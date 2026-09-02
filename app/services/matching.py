"""岗位匹配服务（M 域）：岗位画像向量化 / 双向匹配 / 解释生成 / 储备空缺预警。

职责边界：
- 仅操作岗位匹配域表（pos_position / match_rule / match_result / match_push_log）
- 人才数据（tal_talent / talent_vec）属 T 域，此处**只读复用**，绝不创建/修改
- AI 底座（Ollama/Milvus）通过 app.utils 惰性调用，不可用时给出明确业务错误
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.matching import MatchPushLogDAO, MatchResultDAO, MatchRuleDAO, PosPositionDAO
from app.models.matching import MatchPushLog, MatchResult, MatchRule, PosPosition
from app.utils.response import BusinessError

logger = logging.getLogger("matching")

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
        # 候选池 = top_k*6（向量检索只做粗召回，最终按"匹配度"重新截取 top_k，
        # 避免真正高匹配的人不在最相似的 top_k 里）
        pool = max(top_k * 6, 50)
        for p in positions:
            # 2. 岗位向量（直接 embed 岗位画像文本，保证与入库向量一致）
            qvec = llm.embed(cls.build_profile_text(p))
            hits = vec.search(TALENT_VEC_COLLECTION, qvec, top_k=pool)
            logger.info("[match] position_id=%s hit_raw=%d pool=%d top_k=%d", p.id, len(hits), pool, top_k)
            for h in hits:
                talent_text = h.get("text", "")
                similarity = float(h.get("score", 0.0))
                # 3. 硬过滤
                if not cls._hard_filter_ok(talent_text):
                    logger.info("[match] p=%s skip: empty talent_text", p.id)
                    continue
                # 4. 软加权算分
                score, dims = cls._soft_weighted_score(similarity, talent_text, p, weights)
                # talent_id 从人才画像 text 中解析（T 域约定：text 携带 人才id 标识）
                talent_id = cls._parse_talent_id(talent_text)
                if talent_id <= 0:
                    # 向量缺少【人才id】标记（历史脏向量），无法关联人才 → 跳过，避免用 Milvus id 写库越界
                    logger.info("[match] p=%s skip: no talent_id marker, text=%.60s", p.id, talent_text)
                    continue
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

        # 5. 每岗位按分数降序，只保留匹配度最高的 top_k 个
        per_pos: dict[int, list[dict[str, Any]]] = {}
        for m in matched:
            per_pos.setdefault(m["position_id"], []).append(m)
        kept: list[dict[str, Any]] = []
        for pid, items in per_pos.items():
            items.sort(key=lambda r: r["score"], reverse=True)
            kept.extend(items[:top_k])
        kept.sort(key=lambda r: (r["position_id"], -r["score"]))

        # 6. 落库（幂等：UNIQUE(talent_id, position_id) 已存在则更新）
        # 先跳过已录用(2)/推荐(1) 的历史结论（不算本次新匹配），再对剩余可见候选连续编号 rank
        visible: list[dict[str, Any]] = []
        for m in kept:
            rec = MatchResultDAO.get_by_pair(db, m["talent_id"], m["position_id"])
            if rec and rec.status != 0:
                continue
            visible.append(m)
        logger.info("[match] matched_candidates=%d kept_topk=%d visible=%d",
                    len(matched), len(kept), len(visible))

        saved: list[dict[str, Any]] = []
        pos_rank: dict[int, int] = {}
        for m in visible:
            rank = pos_rank.get(m["position_id"], 0) + 1
            pos_rank[m["position_id"]] = rank
            rec = MatchResultDAO.get_by_pair(db, m["talent_id"], m["position_id"])
            if rec:
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
        logger.info("[match] persisted=%d", len(saved))
        return saved

    @staticmethod
    def _parse_talent_id(text: str, fallback: Any = None) -> int:
        """从人才画像 text 中解析 人才id（T 域约定形如 【人才id:N|学历:...|经验:N年|技能:...】）。

        注意：人才 id 后接 '|' 不是 '】'，正则必须容忍；不要回退到 Milvus 内部 id
        （那是向量自增 id，不是人才 id，超出 match_result.talent_id INT 范围会写库报错）。
        解析不到返回 0（调用方应跳过）。
        """
        m = re.search(r"【人才id[:：](\d+)(?:[\|】])", text or "")
        if m:
            return int(m.group(1))
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

    # 预警去重窗口：同一(匹配结果,类型) 在窗口内只推一次，避免重复点击"生成"刷屏
    ALERT_DEDUPE_HOURS = 24
    # 空缺岗位推送的补位储备人才条数（TopN）
    VACANCY_TOP_N = 3

    @classmethod
    def _alert_dup_in_window(cls, db: Session, match_id: int, alert_type: str) -> bool:
        """判断同一(匹配结果,预警类型) 在去重窗口内是否已生成过预警。"""
        cutoff = datetime.now() - timedelta(hours=cls.ALERT_DEDUPE_HOURS)
        hit = db.scalars(
            select(MatchPushLog.id).where(
                MatchPushLog.match_id == match_id,
                MatchPushLog.type == alert_type,
                MatchPushLog.created_at >= cutoff,
            )
        ).first()
        return hit is not None

    # ===== 空缺岗位补位人才清单（自动推送储备人才） =====

    @staticmethod
    def _warm_text(warm_level: int) -> str:
        return {0: "无保温", 1: "保温低", 2: "保温中", 3: "保温高"}.get(int(warm_level or 0), "无保温")

    @classmethod
    def _vacancy_top_candidates(cls, db: Session, position_id: int,
                                top_n: int | None = None) -> list[MatchResult]:
        """取空缺岗位可补位的 TopN 储备人才（按匹配分降序，剔除已录用 status=2）。"""
        rows = MatchResultDAO.list_by_position(db, position_id, limit=50)
        kept: list[MatchResult] = []
        for rec in rows:
            if rec.status == 2:  # 已录用 → 不再作为补位对象
                continue
            kept.append(rec)
            if len(kept) >= (top_n or cls.VACANCY_TOP_N):
                break
        return kept

    @classmethod
    def _build_vacancy_content(cls, p: PosPosition, vacancy: int,
                               cands: list[MatchResult]) -> str:
        """生成空缺预警消息正文：缺编数 + 可补位储备人才清单（含保温/跟进/达标提示）。"""
        header = f"{p.name} 缺编 {vacancy} 人"
        if len(cands) < vacancy:
            header += f"（暂无足够储备，本次推荐 {len(cands)} 人，建议启动招聘或扩大人才库）"
        header += "，可补位储备人才："
        lines = [header]
        now = datetime.now()
        for i, rec in enumerate(cands, start=1):
            score = float(rec.score)
            flag = "，达标储备" if score >= RESERVE_SCORE_THRESHOLD else "，低于达标线建议评估"
            if rec.last_follow_up:
                days = max(0, int((now - rec.last_follow_up).total_seconds() // 86400))
                follow = "今天跟进" if days == 0 else f"{days} 天前跟进"
                if days > 14:
                    follow += "（超期需加热）"
            else:
                follow = "从未跟进"
            lines.append(
                f"{i}. 人才#{rec.talent_id} 匹配 {score:.1f} 分{flag}"
                f" · {cls._warm_text(rec.warm_level)} · {follow}"
            )
        return "\n".join(lines)

    @classmethod
    def _vacancy_last_message(cls, db: Session, position_id: int) -> tuple[str | None, datetime | None]:
        """取该岗位最近一条空缺预警消息内容与时间（用于内容级去重）。"""
        last = db.scalars(
            select(MatchPushLog)
            .where(
                MatchPushLog.type == "vacancy",
                MatchPushLog.match_id.in_(
                    select(MatchResult.id).where(MatchResult.position_id == position_id)
                ),
            )
            .order_by(MatchPushLog.id.desc())
            .limit(1)
        ).first()
        if not last or not last.message_id:
            return None, None
        from app.models.message import Message
        msg = db.get(Message, last.message_id)
        return (msg.content if msg else None), last.created_at

    @classmethod
    def _vacancy_alert_for(cls, db: Session, p: PosPosition) -> dict[str, Any] | None:
        """对单个空缺岗位生成"补位储备人才"预警（若 24h 内推送内容相同则跳过）。

        推荐数量 = 缺编人数（缺几个推几个），最多不超过 5；如实际候选 < 缺编
        则按实际候选数推，并在内容中提示仍有差额。
        返回新生成的预警 dict；无候选或无变化返回 None。
        """
        vacancy = p.headcount - p.filled
        if vacancy <= 0:
            return None
        n = min(vacancy, 5)  # 缺 N 人推荐 N 人（封顶 5 防刷屏）
        cands = cls._vacancy_top_candidates(db, p.id, top_n=n)
        if not cands:
            return None  # 缺编但无任何候选可推（无法给出补位方案）
        content = cls._build_vacancy_content(p, vacancy, cands)
        last_content, last_at = cls._vacancy_last_message(db, p.id)
        if last_content is not None and last_at is not None:
            within = (datetime.now() - last_at) < timedelta(hours=cls.ALERT_DEDUPE_HOURS)
            if within and last_content == content:
                # 24h 内已推过相同清单 → 不重复打扰（清单变化时内容不同 → 允许重推）
                return None
        alert = cls._write_alert(
            db, rec=cands[0], alert_type="vacancy",
            position_name=p.name,
            msg_title=f"岗位空缺预警：{p.name}",
            msg_content=content,
        )
        alert["position_name"] = p.name
        alert["candidate_count"] = len(cands)
        alert["top_talent_ids"] = [c.talent_id for c in cands]
        return alert

    @classmethod
    def auto_push_vacancy(cls, db: Session, position_ids: list[int]) -> list[dict[str, Any]]:
        """事件自动触发（发起匹配/Agent 岗位匹配成功后调用）：检查岗位缺口并推送补位清单。

        非阻塞：调用方在请求成功后执行；异常在调用处捕获，不影响主流程返回。
        """
        alerts: list[dict[str, Any]] = []
        seen: set[int] = set()
        for pid in position_ids or []:
            if pid in seen:
                continue
            seen.add(pid)
            p = PosPositionDAO.get(db, pid)
            if not p or p.status != 1:
                continue
            alert = cls._vacancy_alert_for(db, p)
            if alert:
                alerts.append(alert)
        if alerts:
            db.commit()
        return alerts

    @classmethod
    def generate_alerts(cls, db: Session, position_id: int | None = None) -> list[dict[str, Any]]:
        """储备/空缺预警（手动生成入口）：空缺岗位补位清单 + 高分储备人才。

        - 空缺预警（vacancy）：编制未满 → 推「补位储备人才 TopN 清单」；
          24h 内同岗位推送内容不变则不重复；清单变化（新晋高分/保温变化）允许重推。
        - 储备预警（reserve）：score >= RESERVE_SCORE_THRESHOLD 且状态为候选(0) 的人才 → 建议纳入储备；
          同一 (match_id, type) 在窗口内不重复。
        - 已录用(status=2)的人才不参与推送。
        """
        positions = (PosPositionDAO.list(db, PosPosition.status == 1, limit=500)
                     if position_id is None else [PosPositionDAO.get(db, position_id)])
        positions = [p for p in positions if p is not None]

        alerts: list[dict[str, Any]] = []
        for p in positions:
            # 空缺预警：编制未满 → 推补位人才清单
            alert = cls._vacancy_alert_for(db, p)
            if alert:
                alerts.append(alert)
            # 储备预警：高分匹配结果（>= 阈值）且仍为候选
            for rec in MatchResultDAO.list_by_position(db, p.id, limit=50):
                if float(rec.score) >= RESERVE_SCORE_THRESHOLD and rec.status == 0:
                    if cls._alert_dup_in_window(db, rec.id, "reserve"):
                        continue
                    alert = cls._write_alert(db, rec, alert_type="reserve",
                                             position_name=p.name,
                                             msg_title=f"储备人才预警：{p.name}",
                                             msg_content=f"人才 #{rec.talent_id} 匹配 {p.name} 达 "
                                                         f"{float(rec.score):.1f} 分（≥{RESERVE_SCORE_THRESHOLD:.0f}），建议纳入保温储备。")
                    alerts.append(alert)
        db.commit()
        return alerts

    @classmethod
    def _write_alert(cls, db: Session, rec: MatchResult, *, alert_type: str,
                     position_name: str | None = None,
                     msg_title: str, msg_content: str) -> dict[str, Any]:
        """写一条预警：msg_center 消息 + match_push_log。

        写入前最终校验（长期护栏）：reserve 储备预警的匹配分必须 ≥ 阈值，
        杜绝未来任何调用路径写出低于触发条件的"假储备"数据。
        """
        if alert_type == "reserve" and float(rec.score) < RESERVE_SCORE_THRESHOLD:
            raise BusinessError(
                400,
                f"储备预警写入被拒绝：需匹配分 ≥ {RESERVE_SCORE_THRESHOLD:.0f}，"
                f"当前 {float(rec.score):.1f} 分（match_id={rec.id}），数据与触发条件不一致。",
            )
        from app.services.message_service import MessageService
        msg = MessageService.send(
            db, type_code="system", title=msg_title, content=msg_content,
            biz_type="matching", biz_id=rec.position_id,
        )
        log = MatchPushLogDAO.create(
            db, match_id=rec.id, type=alert_type, target_user=str(rec.talent_id),
            message_id=msg.id,
        )
        db.flush()
        return {
            "alert_id": log.id, "match_id": rec.id, "type": alert_type,
            "position_id": rec.position_id, "position_name": position_name,
            "talent_id": rec.talent_id, "score": float(rec.score),
            "message_id": msg.id,
        }

    @classmethod
    def list_alerts(cls, db: Session, *, position_id: int | None = None,
                    alert_type: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
        """预警列表（读侧富化）：match_push_log + 匹配结果 + 岗位名 + 消息标题/内容。

        仅做跨表只读关联，不改动其他模块数据。
        """
        where = []
        if alert_type:
            where.append(MatchPushLog.type == alert_type)
        if position_id is not None:
            where.append(MatchPushLog.match_id.in_(
                select(MatchResult.id).where(MatchResult.position_id == position_id)
            ))
        rows = MatchPushLogDAO.list(db, *where, limit=limit,
                                    order_by=MatchPushLog.id.desc())
        if not rows:
            return []

        match_map: dict[int, MatchResult] = {}
        mids = [r.match_id for r in rows if r.match_id]
        if mids:
            for m in db.scalars(select(MatchResult).where(MatchResult.id.in_(mids))).all():
                match_map[m.id] = m

        pos_names: dict[int, str] = {}
        pids = {m.position_id for m in match_map.values() if m.position_id}
        if pids:
            for p in db.scalars(select(PosPosition).where(PosPosition.id.in_(pids))).all():
                pos_names[p.id] = p.name

        msg_map: dict[int, Any] = {}
        mids_2 = [r.message_id for r in rows if r.message_id]
        if mids_2:
            from app.models.message import Message
            for m in db.scalars(select(Message).where(Message.id.in_(mids_2))).all():
                msg_map[m.id] = m

        out: list[dict[str, Any]] = []
        for r in rows:
            m = match_map.get(r.match_id)
            msg = msg_map.get(r.message_id) if r.message_id else None
            out.append({
                "id": r.id, "match_id": r.match_id, "type": r.type,
                "target_user": r.target_user, "message_id": r.message_id,
                "created_at": r.created_at,
                "position_id": m.position_id if m else None,
                "position_name": pos_names.get(m.position_id) if m else None,
                "talent_id": m.talent_id if m else None,
                "score": float(m.score) if m and m.score is not None else None,
                "match_status": m.status if m else None,
                "warm_level": m.warm_level if m else 0,
                "last_follow_up": m.last_follow_up if m else None,
                "msg_title": msg.title if msg else None,
                "msg_content": msg.content if msg else None,
            })
        return out

    # ==================== 储备人才保温管理（需求4） ====================

    @classmethod
    def batch_warm(cls, db: Session, *, match_ids: list[int],
                   warm_level: int) -> list[dict[str, Any]]:
        """批量保温：把多条匹配结果统一设为保温等级并刷新/清空跟进时间。

        warm_level>0：设定等级并刷新 last_follow_up=now（视为一次跟进）；
        warm_level=0：退出保温，清空跟进时间。
        """
        updated: list[dict[str, Any]] = []
        if not match_ids:
            return updated
        now = datetime.now()
        for rec in db.scalars(select(MatchResult).where(MatchResult.id.in_(match_ids))).all():
            rec.warm_level = warm_level
            rec.last_follow_up = now if warm_level > 0 else None
            db.flush()
            updated.append({
                "match_id": rec.id, "warm_level": rec.warm_level,
                "last_follow_up": rec.last_follow_up,
            })
        db.commit()
        return updated

    # ==================== 匹配精度评估（需求2） ====================

    @classmethod
    def evaluate(cls, db: Session, *, position_id: int | None = None,
                 top_k: int = 3,
                 reference: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """匹配精度评估。

        - 有真值 reference=[{position_id, talent_id, is_match}] 时：按 (岗位,人才) 判定命中，
          计算 precision / recall / F1（precision 即用户要求的"匹配精度"）。
          关键参数 top_k：每个岗位只把"算法 TopK 候选"视作"推"，避免被全部 match_result 撑爆分母；
          与 HR 实际"看 top-k 选人"的工作流一致。默认 3。
        - 无真值时：自检口径——对每个岗位取 top1，skill 维度 >=60 视为合理命中，给出参考值。
        """
        where = [MatchResult.status == 0]
        if position_id is not None:
            where.append(MatchResult.position_id == position_id)

        if reference:
            # 按 (position_id, talent_id) 建立真值映射
            truth = {(r["position_id"], r["talent_id"]): bool(r.get("is_match"))
                     for r in reference if "position_id" in r and "talent_id" in r}
            if not truth:
                raise ValueError("reference 缺少 position_id 或 talent_id")

            # "推"的集合：每个岗位按 score 降序取 top_k；这样 precision/recall 与 HR 实际
            # "看 top-k 选人"的工作流匹配，避免被存量的所有 match_result 行拉低分母。
            pos_ids = sorted({r["position_id"] for r in reference})
            top_rows: list = []
            for pid in pos_ids:
                cands = MatchResultDAO.list_by_position(db, pid, limit=top_k)
                top_rows.extend(cands)
            predicted = len(top_rows)
            evaluated = [r for r in top_rows if (r.position_id, r.talent_id) in truth and truth[(r.position_id, r.talent_id)]]
            tp = len(evaluated)
            relevant = sum(1 for v in truth.values() if v)
            precision = tp / predicted if predicted else 0.0
            recall = tp / relevant if relevant else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            return {"mode": "reference", "top_k": top_k,
                    "predicted": predicted, "relevant": relevant, "tp": tp,
                    "precision": round(precision, 4), "recall": round(recall, 4),
                    "f1": round(f1, 4), "precision_pct": round(precision * 100, 2),
                    "note": f"真值评估：每岗取算法 Top{top_k} 候选作为「推」；precision 即匹配精度"}
        else:
            # 自检：每个岗位 top1，skill 维度 >=60 视为合理命中
            pos_ids = [p.id for p in PosPositionDAO.list(db, PosPosition.status == 1, limit=500)]
            hit, total = 0, 0
            for pid in pos_ids:
                top = MatchResultDAO.list_by_position(db, pid, limit=1)
                if not top:
                    continue
                total += 1
                dims = json.loads(top[0].dimension_json or "{}") if top[0].dimension_json else {}
                try:
                    skill = float(dims.get("skill", 0))
                except (TypeError, ValueError):
                    skill = 0.0
                if skill >= 60:
                    hit += 1
            precision = hit / total if total else 0.0
            return {"mode": "self-check", "positions_scored": total, "top1_hit": hit,
                    "precision_pct": round(precision * 100, 2),
                    "note": "自检口径（无人工真值）：top1 且 skill 维度>=60 视为命中；接入人工标注真值后可用 reference 模式得到精确 precision/recall/F1"}
