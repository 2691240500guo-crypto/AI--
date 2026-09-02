"""岗位匹配服务（M 域）：岗位画像向量化 / 双向匹配 / 解释生成 / 储备空缺预警。

职责边界：
- 仅操作岗位匹配域表（pos_position / match_rule / match_result / match_push_log）
- 人才数据（tal_talent / talent_vec）属 T 域，此处**只读复用**，绝不创建/修改
- AI 底座（Ollama/Milvus）通过 app.utils 惰性调用，不可用时给出明确业务错误
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.dao.matching import MatchPushLogDAO, MatchResultDAO, MatchRuleDAO, PosPositionDAO
from app.models.matching import MatchPushLog, MatchResult, MatchRule, PosPosition
from app.utils.response import BusinessError

# Milvus 集合名（VectorStore 会自动加前缀，如 talent_position_vec）
POSITION_VEC_COLLECTION = "position_vec"
TALENT_VEC_COLLECTION = "talent_vec"

# 默认匹配规则权重（skill/degree/years/quality）
DEFAULT_RULE = {"skill": 0.4, "degree": 0.2, "years": 0.2, "quality": 0.2}

# 储备预警分数线
RESERVE_SCORE_THRESHOLD = 80.0


class MatchingService:
    # ==================== 画像构建（T-P4-01 / D02） ====================

    @classmethod
    def build_profile_text(cls, p: PosPosition) -> str:
        """把岗位说明书组装成能力画像文本（向量化输入源）。"""
        parts = [
            f"岗位：{p.name}",
            f"岗位编码：{p.code}",
            f"所属部门：{p.dept_id or '未指定'}",
            f"编制：{p.headcount} 人，已到岗 {p.filled} 人",
        ]
        if p.description:
            parts.append(f"岗位说明书：{p.description}")
        return "；".join(parts)

    @classmethod
    def vectorize_position(cls, db: Session, position_id: int) -> dict[str, Any]:
        """岗位画像向量化：说明书 → bge-m3 embedding → Milvus position_vec。"""
        p = PosPositionDAO.get(db, position_id)
        if not p:
            raise BusinessError(404, "岗位不存在")
        if p.status != 1:
            raise BusinessError(400, f"岗位 {p.name} 已停用，无法向量化")

        try:
            from app.utils.llm import get_llm
            from app.utils.vector_store import get_vector_store

            llm, vec = get_llm(), get_vector_store()
            dim: int | None = None
            if not vec.has_collection(POSITION_VEC_COLLECTION):
                # 用一次真实 embedding 探测维度后建集合（bge-m3=1024）
                dim = len(llm.embed("维度探测"))
                vec.create_collection(POSITION_VEC_COLLECTION, dim=dim)
            text = cls.build_profile_text(p)
            # text 中携带岗位标识，便于检索后反查岗位
            text = f"【岗位id:{p.id}|{p.name}】{text}"
            vec.insert(POSITION_VEC_COLLECTION, [llm.embed(text)], [text])
            if dim is None:  # 集合已存在时，用本次文本 embedding 的维度返回
                dim = len(llm.embed(text))
        except BusinessError:
            raise
        except Exception as e:  # ollama/pymilvus 未装、Milvus 未启动、连接失败等
            raise BusinessError(500, f"岗位向量化失败（检查 Milvus/Ollama 服务与依赖）：{e}")

        return {"position_id": p.id, "vector_dim": dim, "text": text}

    # ==================== 匹配算法（T-P4-02 / D03） ====================

    @classmethod
    def _parse_rule(cls, rule: MatchRule | None) -> dict[str, float]:
        if rule and rule.rule_json:
            try:
                w = json.loads(rule.rule_json)
                if isinstance(w, dict) and w:
                    return {k: float(v) for k, v in w.items()}
            except (ValueError, TypeError):
                pass
        return dict(DEFAULT_RULE)

    @classmethod
    def _hard_filter_ok(cls, talent_text: str) -> bool:
        """硬过滤：人才画像文本有效性校验（MVP 阶段仅排除空画像）。"""
        return bool(talent_text and talent_text.strip())

    @classmethod
    def _keyword_score(cls, talent_text: str, description: str) -> float:
        """技能关键词命中率 → 0-100 分（skill 维度启发式）。"""
        if not description:
            return 60.0  # 无说明书时给中性分
        # 提取说明书中的技术/能力关键词（中英文词）
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fa5]{2,6}", description)
        # 过滤掉常见虚词
        stop = {"岗位", "要求", "负责", "具备", "熟悉", "掌握", "能够", "以及", "或者", "优先", "能力", "相关", "工作"}
        kws = [w for w in words if w not in stop and len(w) > 1]
        if not kws:
            return 60.0
        hit = sum(1 for w in kws if w.lower() in (talent_text or "").lower())
        return round(min(100.0, hit / len(kws) * 100 + 50), 2)

    @classmethod
    def _soft_weighted_score(cls, similarity: float, talent_text: str, p: PosPosition,
                             weights: dict[str, float]) -> tuple[float, dict[str, float]]:
        """软加权算分：向量相似度(基础) + 技能关键词(启发式) → 0-100。"""
        skill = round(min(100.0, similarity * 100), 2)  # IP 相似度 → 百分制
        kw = cls._keyword_score(talent_text, p.description or "")
        skill = round(skill * 0.7 + kw * 0.3, 2)  # 融合关键词启发式，增强可解释性
        degree = 75.0  # MVP：无 T 域学历数据，给中性分（二期接 tal_talent 精确计分）
        years = 75.0
        quality = 75.0
        dims = {"skill": skill, "degree": degree, "years": years, "quality": quality}
        total = sum(dims.get(k, 0.0) * weights.get(k, 0.0) for k in dims)
        return round(min(100.0, total), 2), dims

    @classmethod
    def run_match(cls, db: Session, *, talent_ids: list[int] | None = None,
                  position_ids: list[int] | None = None, rule_id: int | None = None,
                  top_k: int = 10) -> list[dict[str, Any]]:
        """Milvus 向量检索 + 加权算分匹配算法。

        流程：岗位向量 → 检索 talent_vec 召回人才 → 硬过滤 → 软加权 → 排序 → 落库 match_result。
        """
        from app.utils.llm import get_llm
        from app.utils.vector_store import get_vector_store

        try:
            llm, vec = get_llm(), get_vector_store()
        except Exception as e:
            raise BusinessError(500, f"AI 底座不可用（检查 Ollama/Milvus 服务与依赖）：{e}")

        if not vec.has_collection(TALENT_VEC_COLLECTION):
            raise BusinessError(400, "人才向量集合 talent_vec 未就绪（需 T 域先写入人才画像向量）")
        if not vec.has_collection(POSITION_VEC_COLLECTION):
            raise BusinessError(400, "岗位向量集合 position_vec 未就绪，请先执行岗位画像向量化")

        rule = MatchRuleDAO.get(db, rule_id) if rule_id else MatchRuleDAO.default_rule(db)
        weights = cls._parse_rule(rule)

        # 1. 确定待匹配岗位
        if position_ids:
            positions = [PosPositionDAO.get(db, pid) for pid in position_ids]
            positions = [p for p in positions if p and p.status == 1]
        else:
            positions = PosPositionDAO.list(db, PosPosition.status == 1, limit=500)
        if not positions:
            raise BusinessError(400, "没有可匹配的启用岗位")

        matched: list[dict[str, Any]] = []
        for p in positions:
            # 2. 岗位向量（直接 embed 岗位画像文本，保证与入库向量一致）
            qvec = llm.embed(cls.build_profile_text(p))
            hits = vec.search(TALENT_VEC_COLLECTION, qvec, top_k=top_k)
            for h in hits:
                talent_text = h.get("text", "")
                similarity = float(h.get("score", 0.0))
                # 3. 硬过滤
                if not cls._hard_filter_ok(talent_text):
                    continue
                # 4. 软加权算分
                score, dims = cls._soft_weighted_score(similarity, talent_text, p, weights)
                # talent_id 从人才画像 text 中解析（T 域约定：text 携带 人才id 标识，缺失则用 Milvus id）
                talent_id = cls._parse_talent_id(talent_text, h.get("id"))
                if talent_ids and talent_id not in talent_ids:
                    continue
                matched.append({
                    "talent_id": talent_id,
                    "position_id": p.id,
                    "position_name": p.name,
                    "score": score,
                    "dimension_json": json.dumps(dims, ensure_ascii=False),
                    "talent_text": talent_text,
                })

        # 5. 排序（同岗位内按分数降序）
        matched.sort(key=lambda r: (r["position_id"], -r["score"]))
        # 6. 落库（幂等：UNIQUE(talent_id, position_id) 已存在则更新，但已录用/推荐的记录不覆盖）
        saved: list[dict[str, Any]] = []
        # 按岗位分组，组内生成连续 rank
        pos_rank: dict[int, int] = {}
        for m in matched:
            rank = pos_rank.get(m["position_id"], 0) + 1
            pos_rank[m["position_id"]] = rank
            rec = MatchResultDAO.get_by_pair(db, m["talent_id"], m["position_id"])
            if rec:
                if rec.status != 0:  # 已录用(2)/推荐(1) 的结论不因重跑匹配被覆盖
                    saved.append({
                        "match_id": rec.id, "talent_id": m["talent_id"],
                        "position_id": m["position_id"], "position_name": m["position_name"],
                        "score": float(rec.score), "rank": rec.rank or rank,
                        "skipped": True,
                    })
                    continue
                rec.score = m["score"]
                rec.dimension_json = m["dimension_json"]
                rec.rank = rank
                rec.status = 0
            else:
                rec = MatchResultDAO.create(
                    db, talent_id=m["talent_id"], position_id=m["position_id"],
                    score=m["score"], dimension_json=m["dimension_json"],
                    rank=rank, status=0,
                )
            db.flush()
            saved.append({
                "match_id": rec.id, "talent_id": m["talent_id"],
                "position_id": m["position_id"], "position_name": m["position_name"],
                "score": float(m["score"]), "rank": rank, "skipped": False,
            })
        db.commit()
        return saved

    @staticmethod
    def _parse_talent_id(text: str, fallback: Any) -> int:
        """从人才画像 text 中解析 人才id（T 域约定形如 【人才id:12】），失败回退 Milvus id。"""
        m = re.search(r"【人才id[:：](\d+)】", text or "")
        if m:
            return int(m.group(1))
        try:
            return int(fallback)
        except (TypeError, ValueError):
            return 0

    # ==================== 解释生成（T-P4-02 / D04） ====================

    @classmethod
    def explain(cls, db: Session, match_id: int, *, force: bool = False) -> str:
        """匹配解释依据生成：读维度得分 → Ollama 生成可读解释。

        force=True 时强制重新生成；否则已有解释直接返回（避免重复消耗 LLM）。
        """
        rec = MatchResultDAO.get(db, match_id)
        if not rec:
            raise BusinessError(404, "匹配结果不存在")
        if rec.explain and not force:
            return rec.explain
        position = PosPositionDAO.get(db, rec.position_id)
        dims: dict[str, float] = {}
        if rec.dimension_json:
            try:
                dims = {k: float(v) for k, v in json.loads(rec.dimension_json).items()}
            except (ValueError, TypeError):
                pass

        # 找出优势/短板维度
        sorted_dims = sorted(dims.items(), key=lambda kv: kv[1], reverse=True)
        strength = sorted_dims[:2]
        weakness = sorted_dims[-2:] if len(sorted_dims) > 2 else []

        prompt = (
            f"岗位「{position.name if position else rec.position_id}」匹配一位人才，综合匹配度 {float(rec.score):.1f} 分。\n"
            f"各维度得分：{dims}\n"
            f"请用中文生成 80 字以内的匹配解释，说明：匹配依据（优势维度）、可能短板、以及是否推荐录用（≥80 推荐）。"
        )
        from app.utils.llm import get_llm
        try:
            explanation = get_llm().chat(prompt, system="你是资深 HR 岗位匹配分析专家，输出简洁客观。")
        except Exception:
            # LLM 不可用时降级为规则化解释
            strength_txt = "、".join(f"{k}({v:.0f}分)" for k, v in strength) or "暂无"
            weakness_txt = "、".join(f"{k}({v:.0f}分)" for k, v in weakness) or "无明显短板"
            explanation = (
                f"匹配度 {float(rec.score):.1f} 分。优势维度：{strength_txt}；短板维度：{weakness_txt}。"
                f"{'建议推荐' if rec.score >= 80 else '建议作为储备候选'}。"
            )
        rec.explain = explanation
        db.commit()
        return explanation

    # ==================== 储备/空缺预警（T-P4-02 / D05） ====================

    @classmethod
    def generate_alerts(cls, db: Session, position_id: int | None = None) -> list[dict[str, Any]]:
        """储备/空缺预警：空缺岗位 + 高分储备人才 → 写 match_push_log + 发消息。"""
        from app.services.message_service import MessageService

        positions = (PosPositionDAO.list(db, PosPosition.status == 1, limit=500)
                     if position_id is None else [PosPositionDAO.get(db, position_id)])
        positions = [p for p in positions if p is not None]

        alerts: list[dict[str, Any]] = []
        for p in positions:
            vacancy = p.headcount - p.filled
            # 空缺预警：编制未满 → 取该岗位高分候选作为替补推荐
            if vacancy > 0:
                top = MatchResultDAO.list_by_position(db, p.id, limit=5)
                for rec in top[:1]:  # 每个空缺岗位推最高分候选
                    alert = cls._write_alert(db, rec, alert_type="vacancy",
                                             msg_title=f"岗位空缺预警：{p.name}",
                                             msg_content=f"{p.name} 缺编 {vacancy} 人，候选人才 #{rec.talent_id} 匹配度 {float(rec.score):.1f} 分，建议跟进。")
                    alerts.append(alert)
            # 储备预警：高分匹配结果（>= 阈值）
            for rec in MatchResultDAO.list_by_position(db, p.id, limit=50):
                if float(rec.score) >= RESERVE_SCORE_THRESHOLD and rec.status == 0:
                    alert = cls._write_alert(db, rec, alert_type="reserve",
                                             msg_title=f"储备人才预警：{p.name}",
                                             msg_content=f"人才 #{rec.talent_id} 匹配 {p.name} 达 {float(rec.score):.1f} 分（≥{RESERVE_SCORE_THRESHOLD:.0f}），建议纳入储备。")
                    alerts.append(alert)
        db.commit()
        return alerts

    @classmethod
    def _write_alert(cls, db: Session, rec: MatchResult, *, alert_type: str,
                     msg_title: str, msg_content: str) -> dict[str, Any]:
        """写一条预警：msg_center 消息 + match_push_log。"""
        from app.services.message_service import MessageService
        hr_user_ids = MessageService.hr_user_ids(db)
        msg = None
        if hr_user_ids:
            msg = MessageService.send(
                db, type_code="system", title=msg_title, content=msg_content,
                receiver_ids=hr_user_ids, biz_type="matching", biz_id=rec.position_id,
            )
        log = MatchPushLogDAO.create(
            db, match_id=rec.id, type=alert_type, target_user=str(rec.talent_id),
            message_id=msg.id if msg else None,
        )
        db.flush()
        return {
            "alert_id": log.id, "match_id": rec.id, "type": alert_type,
            "position_id": rec.position_id, "talent_id": rec.talent_id,
            "score": float(rec.score), "message_id": msg.id if msg else None,
        }
