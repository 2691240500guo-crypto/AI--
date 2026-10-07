"""简历上传服务（批次 2.3a）。

链路：
    1. 校验文件类型 / 大小
    2. 把原件落到 MinIO（复用基座 ObjectStorage）
    3. 抽文本（pdf/docx/image/txt/md）
    4. 创建 /biz_talent/ 草稿记录（source=import，raw_text=抽出的文本）
    5. 触发规则版自动打标签（TalentAutoTagger）
    6. 返回新 talent

链路后续由批次 2.3b 调用 LLM、2.3c 写入向量库 —— 这里**只负责上传+抽取+落主档**，
跑通后整条 Agent① 链路在 2.3b 接入。

仅本模块新增。
"""
# hq新增内容 - 人才档案批次 2.3a
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.dao.talent import TalentDAO, TalentTagRelDAO
from app.models.talent import Talent
from app.services.talent_tag_service import TalentAutoTagger
from app.utils.file_parser import detect_kind, is_supported, parse_bytes
from app.utils.object_storage import get_object_storage
from app.utils.response import BusinessError

logger = logging.getLogger(__name__)


# MinIO 子目录前缀，便于按日期归档
_PREFIX = "resume"


class ResumeUploadService:
    """简历上传 + 抽取 + 落库。"""

    @staticmethod
    def _normalize_suffix(filename: str) -> str:
        """从文件名提后缀（小写、含点）。"""
        if "." not in filename:
            raise BusinessError(400, "文件缺少扩展名")
        return "." + filename.rsplit(".", 1)[-1].lower()

    @classmethod
    def handle(cls, db: Session, *, content: bytes, filename: str, content_type: str = "application/octet-stream") -> Talent:
        """处理上传。

        :return: 新建/创建的 talent
        """
        suffix = cls._normalize_suffix(filename)
        if not is_supported(suffix):
            raise BusinessError(400, f"暂不支持的文件类型：{suffix}")

        # 1) 落 MinIO
        storage = get_object_storage()
        date_prefix = datetime.now().strftime("%Y/%m")
        obj_name = f"{_PREFIX}/{date_prefix}/{uuid.uuid4().hex}{suffix}"
        try:
            storage.put_bytes(obj_name, content, content_type=content_type)
        except Exception as e:  # pragma: no cover
            logger.exception("[hq] MinIO 上传失败：%s", e)
            raise BusinessError(500, f"对象存储上传失败：{e}") from e

        # 2) 抽文本
        try:
            text = parse_bytes(content, suffix)
        except (RuntimeError, ValueError, FileNotFoundError) as e:
            raise BusinessError(400, f"文件解析失败：{e}") from e

        if not text:
            raise BusinessError(400, "未能从文件抽到任何文字，请检查文件内容或格式")

        # 3) 落库（草稿，姓名兜底「未命名-<id>」，resume_source=import）
        # hq+  批次补充：原始附件 MinIO 对象键正式写入 object_key 字段，
        #      resume_text 只保留抽出的文本（不再塞 [object_key=...] 前缀）
        # 2026-09-01 合并：source→resume_source、raw_text→resume_text（tal_talent 字段）
        obj = TalentDAO.create(
            db,
            name=f"未命名-{datetime.now().strftime('%H%M%S')}",
            resume_source="import",
            resume_text=text,
            object_key=obj_name,
        )

        db.flush()

        # 4) 跑规则版自动打标签（tal_tag + tal_talent_tag）
        auto_ids = TalentAutoTagger.auto_tag(db, obj)
        if auto_ids:
            TalentTagRelDAO.set_ai_tags(db, obj.id, auto_ids)

        db.commit()
        db.refresh(obj)
        logger.info("[hq] 简历已入库：talent_id=%s, kind=%s, chars=%d",
                    obj.id, detect_kind(suffix), len(text))

        # hq+  批次2.3b：抽完后立即触发 LLM 解析（失败不阻塞，错误写到 report 表）
        try:
            from app.services.resume_llm_service import ResumeLLMService  # hq+
            result = ResumeLLMService.apply(db, obj, text)
            logger.info("[hq] LLM 解析完成：talent_id=%s, ai_tags=%d",
                        obj.id, result.get("new_tag_count"))
        except Exception as e:
            logger.warning("[hq] LLM 解析失败（不影响入库）：%s", e)
            # 写一条伪报告记录失败原因，前端可读 report 字段告知
            from app.dao.talent_report import TalentReportDAO  # hq+
            TalentReportDAO.upsert(db, obj.id, {
                "parsed_json": None,
                "summary_report": f"（AI 解析失败：{e}，可手动重跑）",
            })
            db.commit()

        # hq+  批次C：LLM 抽取后做去重检测（命中则前端统一弹确认框人工确认）
        duplicate = None
        try:
            from app.services.talent_dedup_service import TalentDedupService  # hq+
            dup = TalentDedupService.detect_duplicate(db, obj)
            if dup.get("matched"):
                old = dup.get("old_talent")
                duplicate = {
                    "matched": True,
                    "type": dup.get("type"),
                    "new_talent_id": obj.id,
                    "old_talent_id": old.id if old else None,
                    "old_name": old.name if old else None,
                    "old_phone": old.phone if old else None,
                    "old_company": old.current_company if old else None,
                }
                db.commit()
        except Exception as e:
            logger.warning("[hq] 去重检测失败（不影响入库）：%s", e)

        # hq+  2026-09-01：上传即自动写四维向量（含简历原文维），语义搜索可直接按简历内容召回
        try:
            from app.services.talent_vector_service import upsert_talent_vectors  # hq+
            ok_dims = upsert_talent_vectors(obj)
            logger.info("[hq] 上传自动向量化 talent_id=%s 成功维度=%s", obj.id, list(ok_dims.keys()))
        except Exception as e:
            logger.warning("[hq] 上传后自动向量化失败（不影响入库）：%s", e)

        # hq+  2026-09-03：新档案自动出岗位匹配结果（M 域联动，失败不影响上传流程）
        try:
            from app.services.matching import MatchingService
            result = MatchingService.auto_match_new_talent(db, int(obj.id))
            logger.info("[hq] 上传建档后自动匹配 talent_id=%s: %s", obj.id, result)
        except Exception as e:
            logger.warning("[hq] 上传后自动匹配失败（不影响入库）：%s", e)

        # M1 知识图谱：LLM 解析 + 标签落库后同步人才子图（Neo4j 不可用自动降级）
        from app.services.kg_sync import safe_sync_talent
        safe_sync_talent(db, int(obj.id), source="简历上传")

        db.refresh(obj)
        return obj, duplicate
