"""人才去重服务（批次 C）。

核心逻辑：
1. ``detect_duplicate(db, talent)``：用 name / phone 与库内档案比对，返回匹配结果
    - double（姓名+电话都命中同一人）→ 建议直接覆盖
    - name / phone（仅单条件命中）→ 建议进人工审核
2. ``overwrite(db, new_id, old_id)``：用新档案字段覆盖旧档案，软删新档案，
   重打标签 + 重算三维向量（旧档案保留原 id，避免引用断裂）

仅本模块新增。
"""
# hq新增内容 - 人才档案批次C
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.dao.talent import TalentDAO
from app.dao.talent_merge import TalentMergeDAO
from app.models.talent import Talent
from app.models.talent_merge import TalentMerge
from app.services.talent_tag_service import TalentAutoTagger
from app.utils.response import BusinessError

logger = logging.getLogger(__name__)


def _norm(s: str | None) -> str:
    return (s or "").strip()


class TalentDedupService:
    """人才去重检测 + 覆盖。"""

    @staticmethod
    def detect_duplicate(db: Session, talent: Talent) -> dict:
        """检测新档案与库内档案的重复情况（上传时调用，直接返回结果给前端弹框）。

        简化版（按用户要求）：不再区分 double/name/phone 建审核队列，
        只要命中重复就把旧档案信息返回，由前端统一弹确认框让用户人工决定。
        match_type 仍标注便于前端文案：double=姓名+电话 / name=仅姓名 / phone=仅电话

        :return: {"matched": bool, "type": "double"|"name"|"phone"|None,
                  "old_talent": Talent | None}
        """
        name = _norm(talent.name)
        phone = _norm(talent.phone)
        # 未命名草稿（LLM 没抽到姓名）不做匹配
        if not name or name.startswith("未命名-"):
            return {"matched": False, "type": None, "old_talent": None}

        by_name = TalentDAO.get_by_name(db, name)
        by_phone = TalentDAO.get_by_phone(db, phone) if phone else None

        old: Talent | None = None
        match_type: str | None = None

        # 双条件：同一人同时命中 name 和 phone
        if by_name and by_phone and by_name.id == by_phone.id and by_name.id != talent.id:
            old, match_type = by_name, "double"
        # 仅姓名命中（且不是自己）
        elif by_name and by_name.id != talent.id:
            old, match_type = by_name, "name"
        # 仅电话命中（且不是自己）
        elif by_phone and by_phone.id != talent.id:
            old, match_type = by_phone, "phone"

        if not old:
            return {"matched": False, "type": None, "old_talent": None}
        return {"matched": True, "type": match_type, "old_talent": old}

    @staticmethod
    def overwrite(db: Session, new_id: int, old_id: int, *,
                  remark: str = "") -> Talent:
        """用新档案覆盖旧档案。

        - 旧档案保留 id（标签/向量引用不失效）
        - 新档案字段覆盖旧档案（姓名/电话/邮箱/职称/公司/年限/学历/简介/原文/附件）
        - 新档案软删（status=0）
        - 重打规则标签（保留已有标签并合并）
        - 重算三维向量（动态更新画像）
        """
        if new_id == old_id:
            raise BusinessError(400, "新档案与旧档案不能是同一档案")
        new_t = TalentDAO.get(db, new_id)
        old_t = TalentDAO.get(db, old_id)
        if not new_t or not old_t:
            raise BusinessError(404, "档案不存在")

        # 1) 字段覆盖（object_key/resume_text 等用新的；字段对齐 tal_talent）
        old_t.name = new_t.name
        old_t.gender = new_t.gender
        old_t.birth_year = new_t.birth_year
        old_t.phone = new_t.phone
        old_t.email = new_t.email
        old_t.current_title = new_t.current_title
        old_t.highest_education = new_t.highest_education
        old_t.years_experience = new_t.years_experience
        old_t.current_company = new_t.current_company
        old_t.summary = new_t.summary
        old_t.resume_text = new_t.resume_text
        old_t.skills = new_t.skills
        old_t.work_experience = new_t.work_experience
        old_t.project_experience = new_t.project_experience
        old_t.honors = new_t.honors
        old_t.object_key = new_t.object_key
        old_t.resume_source = new_t.resume_source
        db.flush()

        # 2) 规则标签合并（旧档案已有标签保留，仅补新命中的；tal_tag + tal_talent_tag）
        from app.dao.talent import TalentTagRelDAO  # hq+
        from app.models.talent import TalentTalentTag  # hq+
        auto_ids = TalentAutoTagger.auto_tag(db, old_t)
        if auto_ids:
            existing = {r.tag_id for r in db.query(TalentTalentTag)
                        .filter(TalentTalentTag.talent_id == old_t.id).all()}
            merged = [i for i in auto_ids if i not in existing]
            if merged:
                TalentTagRelDAO.set_ai_tags(db, old_t.id, merged)

        # 3) 软删新档案
        TalentService_soft_delete(db, new_t)

        # 4) 重算三维向量
        try:
            from app.dao.talent_report import TalentReportDAO  # hq+
            from app.services.talent_vector_service import upsert_talent_vectors  # hq+
            report = TalentReportDAO.get_by(db, talent_id=old_t.id)
            upsert_talent_vectors(old_t, report)
        except Exception as e:
            logger.warning("[hq] 覆盖后重算向量失败：%s", e)

        db.flush()
        return old_t


def TalentService_soft_delete(db: Session, obj: Talent) -> None:
    """内联软删（避免循环 import 正式 TalentService）。"""
    obj.status = 0
    db.flush()
