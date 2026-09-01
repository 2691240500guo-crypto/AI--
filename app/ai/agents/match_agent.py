"""岗位人才匹配 Agent（M 域核心 AI 能力）。

职责（对齐《AI岗位人才智能匹配模块》需求）：
1. 岗位智能解析：LLM 拆解岗位任职要求/技能标准/经验门槛/学历要求/综合素质 → 标准化标签体系
2. 双向精准匹配：岗位→人才（run_match）、人才→岗位（reverse_match），0-100 分
3. 双重策略打分：硬性条件过滤（学历/经验/必备技能）+ 软性能力加权（skill/degree/years/quality）
4. 候选人才排序 + 匹配原因解释（复用 MatchingService.explain）

AI 底座：硅基流动 Qwen3-30B（chat）+ bge-m3（embed，1024 维）+ Milvus（talent_vec/position_vec）。

人才画像 text 约定（scripts/vectorize_talents.py 写入）：
    【人才id:35|学历:硕士|经验:3年|技能:Python,Java,SQL】姓名：...；专业：...；...
硬过滤依赖该结构化标记。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.dao.matching import MatchResultDAO, PosPositionDAO
from app.models.matching import PosPosition
from app.services.matching import DEFAULT_RULE, MatchingService
from app.utils.response import BusinessError

POSITION_VEC_COLLECTION = "position_vec"
TALENT_VEC_COLLECTION = "talent_vec"

# 学历等级（数值越大越高）
DEGREE_LEVEL = {"博士": 4, "硕士": 3, "本科": 2, "大专": 1, "中专": 1, "高中": 0}
UNKNOWN_DEGREE = -1

# 结构化标记正则：【人才id:35|学历:硕士|经验:3年|技能:Python,Java,SQL】
_TALENT_META_RE = re.compile(
    r"【人才id[:：](\d+)\|学历[:：]([^|]*)\|经验[:：](\d+)年\|技能[:：]([^】]*)】"
)


class MatchAgent:
    # ==================== 岗位需求智能解析 ====================

    @classmethod
    def parse_requirement(cls, db: Session, position_id: int) -> dict[str, Any]:
        """岗位智能解析：LLM 拆解核心要求/技能标准/经验门槛/学历要求/综合素质。

        LLM 不可用时降级规则化提取（关键词 + 正则），保证功能可用。
        """
        p = PosPositionDAO.get(db, position_id)
        if not p:
            raise BusinessError(404, "岗位不存在")
        if not p.description and not p.name:
            raise BusinessError(400, "岗位缺少名称与岗位说明书，无法解析")

        prompt = (
            "你是资深岗位分析师。请根据岗位信息拆解任职要求，输出**纯 JSON**（不要 markdown 代码块），格式：\n"
            '{"core_requirements":["核心职责/要求，2-4条"],"skill_standards":["技能标准，如 Python"],'
            '"experience_threshold":{"years":3,"text":"3年以上"},"degree_threshold":"本科",'
            '"quality_dimensions":["综合素质维度，2-3个"],"tags":["标准化标签，5-10个"]}\n'
            "注意：经验年限用数字；学历阈值用 博士/硕士/本科/大专/不限；信息不足的字段填空值。\n"
            f"岗位名称：{p.name}\n岗位编码：{p.code}\n岗位说明书：{p.description or '（无）'}"
        )
        parsed: dict[str, Any] | None = None
        try:
            from app.utils.llm import get_llm

            raw = get_llm().chat(prompt, system="只输出合法 JSON，不要任何解释文字。")
            parsed = cls._extract_json(raw)
        except Exception:  # noqa: BLE001
            parsed = None

        if not parsed:
            parsed = cls._rule_based_parse(p)  # LLM 失败 → 规则化兜底

        return {
            "position_id": p.id,
            "title": p.name,
            "code": p.code,
            "core_requirements": parsed.get("core_requirements", []),
            "skill_standards": parsed.get("skill_standards", []),
            "experience_threshold": parsed.get("experience_threshold", {"years": 0, "text": "不限"}),
            "degree_threshold": parsed.get("degree_threshold", "不限"),
            "quality_dimensions": parsed.get("quality_dimensions", []),
            "tags": parsed.get("tags", []),
        }

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        """从 LLM 输出中稳健提取 JSON（容忍 markdown 代码块/前后噪音）。"""
        if not raw:
            return None
        text = raw.strip()
        # 剥离 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except ValueError:
            pass
        # 尝试截取首个 { ... } 块
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else None
            except ValueError:
                return None
        return None

    @classmethod
    def _rule_based_parse(cls, p: PosPosition) -> dict[str, Any]:
        """规则化兜底解析：正则提取技能关键词、经验年限。"""
        desc = p.description or ""
        # 经验年限：匹配 "X年以上/X年经验" 等
        years = 0
        m = re.search(r"(\d+)\s*年", desc)
        if m:
            years = int(m.group(1))
        # 技能关键词：中文2-6字 / 英文token（过滤虚词）
        stop = {"岗位", "要求", "负责", "具备", "熟悉", "掌握", "能够", "以及", "或者", "优先",
                "能力", "相关", "工作", "学历", "经验", "以上", "本科", "硕士", "开发", "设计"}
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fa5]{2,6}", desc)
        skills = [w for w in words if w not in stop and len(w) > 1]
        # 学历阈值
        degree = "不限"
        for d in ("博士", "硕士", "本科", "大专"):
            if d in desc:
                degree = d
                break
        tags = skills[:8] + ([f"{years}年经验"] if years else []) + ([degree] if degree != "不限" else [])
        return {
            "core_requirements": [desc[:80]] if desc else [],
            "skill_standards": skills[:12],
            "experience_threshold": {"years": years, "text": f"{years}年以上" if years else "不限"},
            "degree_threshold": degree,
            "quality_dimensions": [],
            "tags": tags,
        }

    # ==================== 人才画像解析（硬过滤基础） ====================

    @staticmethod
    def _parse_talent_meta(text: str) -> dict[str, Any]:
        """从人才画像 text 解析结构化标记：id/学历/经验/技能。"""
        m = _TALENT_META_RE.search(text or "")
        if not m:
            return {"talent_id": 0, "degree": "", "years": 0, "skills": []}
        skills = [s.strip() for s in m.group(4).split(",") if s.strip()]
        return {
            "talent_id": int(m.group(1)),
            "degree": m.group(2).strip(),
            "years": int(m.group(3) or 0),
            "skills": skills,
        }

    # ==================== 双重策略打分 ====================

    @classmethod
    def _degree_score(cls, talent_degree: str, require_degree: str) -> float:
        """学历维度：达到要求 90，高于 100，低于 50，未知/不限 75。"""
        if not require_degree or require_degree in ("不限", "未知"):
            return 75.0
        t = DEGREE_LEVEL.get(talent_degree, UNKNOWN_DEGREE)
        r = DEGREE_LEVEL.get(require_degree, UNKNOWN_DEGREE)
        if t == UNKNOWN_DEGREE:
            return 70.0
        if t >= r:
            return 100.0 if t > r else 90.0
        return max(30.0, 50.0 - (r - t) * 10)

    @classmethod
    def _years_score(cls, talent_years: int, require_years: int) -> float:
        """经验维度：达标 90，超出加分（封顶 100），不足按差额扣分，未知/无要求 75。"""
        if not require_years:
            return 75.0
        if talent_years <= 0:
            return 65.0
        if talent_years >= require_years:
            return min(100.0, 90.0 + (talent_years - require_years) * 5)
        return max(30.0, 90.0 - (require_years - talent_years) * 10)

    @classmethod
    def _skill_score(cls, talent_skills: list[str], skill_standards: list[str],
                     similarity: float) -> float:
        """技能维度：向量相似度 ×0.6 + 技能标准命中率 ×0.4 → 0-100。"""
        sim_score = min(100.0, similarity * 100)
        if not skill_standards:
            return round(sim_score, 2)
        low = [s.lower() for s in talent_skills]
        hit = sum(1 for s in skill_standards if any(s.lower() in t or t in s.lower() for t in low))
        hit_score = min(100.0, hit / len(skill_standards) * 100 + 40) if hit else 30.0
        return round(sim_score * 0.6 + hit_score * 0.4, 2)

    @classmethod
    def _quality_score(cls, similarity: float, talent_text: str) -> float:
        """综合素质维度：MVP 阶段以语义相似度 + 画像完整度近似，二期接测评数据。"""
        base = min(100.0, similarity * 100)
        # 画像信息越完整（有经历/自我评价），综合素质分越高
        bonus = 0.0
        for key in ("工作经历", "项目经历", "自我评价", "荣誉"):
            if key in (talent_text or ""):
                bonus += 3.0
        return round(min(100.0, base * 0.8 + 70 * 0.2 + bonus), 2)

    @classmethod
    def _hard_filter(cls, meta: dict[str, Any], req: dict[str, Any]) -> tuple[bool, str]:
        """硬性条件过滤：学历门槛 / 经验门槛 / 必备技能。

        返回 (是否通过, 未通过原因)。未知信息默认放行（避免误杀），由软性分体现差距。
        """
        # 学历门槛
        degree_req = req.get("degree_threshold", "不限")
        if degree_req and degree_req not in ("不限", "未知"):
            t = DEGREE_LEVEL.get(meta.get("degree", ""), UNKNOWN_DEGREE)
            r = DEGREE_LEVEL.get(degree_req, UNKNOWN_DEGREE)
            if t != UNKNOWN_DEGREE and t < r:
                return False, f"学历不达标（要求{degree_req}，实际{meta.get('degree','未知')}）"
        # 经验门槛
        years_req = (req.get("experience_threshold") or {}).get("years", 0) or 0
        if years_req > 0 and 0 < meta.get("years", 0) < years_req:
            return False, f"经验不足（要求{years_req}年，实际{meta.get('years', 0)}年）"
        # 必备技能（前端筛选覆盖项）
        mandatory = req.get("mandatory_skills") or []
        if mandatory:
            talent_skills = meta.get("skills", [])
            hit_any = any(
                any(m.lower() in s.lower() or s.lower() in m.lower() for s in talent_skills)
                for m in mandatory
            )
            if not hit_any:
                return False, f"缺少必备技能：{'/'.join(mandatory)}"
        return True, ""

    # ==================== 岗位 → 人才匹配 ====================

    @classmethod
    def run_match(cls, db: Session, position_id: int, *, top_k: int = 10,
                  parse: bool = True, gen_explain: bool = True,
                  min_score: float = 0.0,
                  filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """岗位→人才匹配：解析需求 → 向量检索 → 硬过滤 → 软加权 → 排序 → 落库。

        filters 可选覆盖项：degree_required / years_required / mandatory_skills。
        """
        p = PosPositionDAO.get(db, position_id)
        if not p:
            raise BusinessError(404, "岗位不存在")

        # 1. 岗位需求解析（LLM 结构化 or 规则兜底）
        req = cls.parse_requirement(db, position_id) if parse else cls._rule_based_parse(p)
        # 前端筛选覆盖（硬过滤门槛）
        if filters:
            if filters.get("degree_required"):
                req["degree_threshold"] = filters["degree_required"]
            if filters.get("years_required") is not None:
                req["experience_threshold"] = {
                    "years": int(filters["years_required"]),
                    "text": f"{filters['years_required']}年以上",
                }
            if filters.get("mandatory_skills"):
                req["mandatory_skills"] = filters["mandatory_skills"]

        from app.utils.llm import get_llm
        from app.utils.vector_store import get_vector_store

        try:
            llm, vec = get_llm(), get_vector_store()
        except Exception as e:  # noqa: BLE001
            raise BusinessError(500, f"AI 底座不可用：{e}") from e

        if not vec.has_collection(TALENT_VEC_COLLECTION):
            raise BusinessError(400, "人才向量集合 talent_vec 未就绪，请先运行 scripts/vectorize_talents.py")

        # 2. 岗位向量 → Milvus 高维语义检索
        qvec = llm.embed(MatchingService.build_profile_text(p))
        hits = vec.search(TALENT_VEC_COLLECTION, qvec, top_k=top_k * 3)

        # 3. 硬过滤 + 4. 软加权 + 5. 排序
        results: list[dict[str, Any]] = []
        for h in hits:
            talent_text = h.get("text", "")
            similarity = float(h.get("score", 0.0))
            meta = cls._parse_talent_meta(talent_text)
            ok_flag, reason = cls._hard_filter(meta, req)
            if not ok_flag:
                continue
            skill = cls._skill_score(meta["skills"], req.get("skill_standards", []), similarity)
            degree = cls._degree_score(meta.get("degree", ""), req.get("degree_threshold", "不限"))
            years = cls._years_score(meta.get("years", 0), (req.get("experience_threshold") or {}).get("years", 0))
            quality = cls._quality_score(similarity, talent_text)
            weights = DEFAULT_RULE
            dims = {"skill": skill, "degree": degree, "years": years, "quality": quality}
            total = round(min(100.0, sum(dims[k] * weights.get(k, 0) for k in dims)), 2)
            results.append({
                "talent_id": meta["talent_id"],
                "position_id": p.id,
                "position_name": p.name,
                "score": total,
                "dimension_json": json.dumps(dims, ensure_ascii=False),
                "talent_text": talent_text,
                "degree": meta.get("degree", ""),
                "years": meta.get("years", 0),
                "skills": meta.get("skills", []),
            })

        # 按分数降序 + min_score 过滤
        results.sort(key=lambda r: r["score"], reverse=True)
        results = [r for r in results if r["score"] >= min_score][:top_k]

        # 6. 落库 match_result（幂等，已推荐/录用不覆盖）
        saved: list[dict[str, Any]] = []
        for rank, m in enumerate(results, start=1):
            rec = MatchResultDAO.get_by_pair(db, m["talent_id"], m["position_id"])
            if rec and rec.status != 0:
                continue  # 已推荐/录用结论保留
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
            item = {
                "match_id": rec.id, "rank": rank,
                "talent_id": m["talent_id"], "position_id": m["position_id"],
                "position_name": m["position_name"],
                "score": m["score"], "dimension_json": m["dimension_json"],
                "talent_text": m["talent_text"],
            }
            # 解释生成（LLM 失败自动降级规则化）
            if gen_explain:
                try:
                    item["explain"] = MatchingService.explain(db, rec.id, force=False)
                except Exception:  # noqa: BLE001
                    item["explain"] = ""
            saved.append(item)
        db.commit()
        return saved

    # ==================== 人才 → 岗位 反向匹配 ====================

    @classmethod
    def reverse_match(cls, db: Session, talent_id: int, *, top_k: int = 10,
                      min_score: float = 0.0) -> list[dict[str, Any]]:
        """人才→岗位反向匹配：人才画像向量 → 检索 position_vec → 打分排序。"""
        from app.utils.llm import get_llm
        from app.utils.vector_store import get_vector_store

        try:
            llm, vec = get_llm(), get_vector_store()
        except Exception as e:  # noqa: BLE001
            raise BusinessError(500, f"AI 底座不可用：{e}") from e

        # 从 MySQL 读人才档案组装画像（与 vectorize_talents.py 一致）
        from sqlalchemy import text as sa_text

        row = db.execute(sa_text("SELECT * FROM tal_talent WHERE id=:tid"), {"tid": talent_id}).mappings().first()
        if not row:
            raise BusinessError(404, "人才不存在")

        def _norm(v) -> str:
            return "" if v is None else str(v).strip()

        skills = _norm(row["skills"]).replace(";", ",").replace("；", ",")
        degree = _norm(row["highest_education"]) or "未知"
        years_m = re.search(r"(\d+)", _norm(row["years_experience"]))
        years = years_m.group(1) if years_m else "0"
        talent_text = (
            f"【人才id:{talent_id}|学历:{degree}|经验:{years}年|技能:{skills}】"
            f"姓名：{_norm(row['name'])}；专业：{_norm(row['major'])}；"
            f"从业经验：{_norm(row['years_experience'])}；技能：{skills}"
        )
        qvec = llm.embed(talent_text)
        hits = vec.search(POSITION_VEC_COLLECTION, qvec, top_k=top_k * 2)

        results: list[dict[str, Any]] = []
        for h in hits:
            ptext = h.get("text", "")
            similarity = float(h.get("score", 0.0))
            pid_m = re.search(r"【岗位id[:：](\d+)", ptext)
            pid = int(pid_m.group(1)) if pid_m else 0
            p = PosPositionDAO.get(db, pid) if pid else None
            if not p:
                continue
            # 岗位需求解析（LLM 有成本，反向匹配用规则兜底快速打分）
            req = cls._rule_based_parse(p)
            skill = cls._skill_score(
                [s.strip() for s in skills.split(",") if s.strip()],
                req.get("skill_standards", []), similarity,
            )
            degree_score = cls._degree_score(degree, req.get("degree_threshold", "不限"))
            years_score = cls._years_score(int(years), req.get("experience_threshold", {}).get("years", 0))
            quality = cls._quality_score(similarity, talent_text)
            dims = {"skill": skill, "degree": degree_score, "years": years_score, "quality": quality}
            total = round(min(100.0, sum(dims[k] * DEFAULT_RULE.get(k, 0) for k in dims)), 2)
            results.append({
                "position_id": p.id,
                "position_name": p.name,
                "score": total,
                "dimension_json": json.dumps(dims, ensure_ascii=False),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return [r for r in results if r["score"] >= min_score][:top_k]

    # ==================== 自然语言操作（NL → 意图 → 执行 → 回复） ====================

    @classmethod
    def chat(cls, db: Session, message: str) -> dict[str, Any]:
        """自然语言操作入口：意图识别 → 参数抽取 → 实体映射 → 执行 → 自然语言回复。

        支持意图：
        - parse    解析岗位需求（"分析XX岗位的要求"）
        - match    岗位→人才匹配（"找适合XX的人才，要求…"）
        - reverse  人才→岗位反向匹配（"人才X适合什么岗位"）
        - explain  匹配依据解释（"为什么人才X排第一" / "人才X和岗位Y的匹配原因"）
        - unknown  无法理解 → 返回帮助文案
        """
        from app.utils.llm import get_llm

        llm = get_llm()
        # 1. 意图识别 + 参数抽取（LLM 输出结构化 JSON）
        parsed = cls._nlp_parse(db, message)
        intent = parsed.get("intent", "unknown")
        filters = parsed.get("filters") or {}

        # 2. 实体映射：岗位名/人才名 → 库中记录
        position = cls._resolve_position(db, parsed.get("position"))
        talent = cls._resolve_talent(db, parsed.get("talent"))
        pid = position["id"] if position else None
        tid = talent["id"] if talent else None

        # 3. 按意图执行
        result: dict[str, Any] = {"intent": intent, "params": parsed, "result": None}
        try:
            if intent == "parse" and pid:
                data = cls.parse_requirement(db, pid)
                result["result"] = data
            elif intent == "match" and pid:
                data = cls.run_match(db, pid, top_k=10, gen_explain=True, filters=filters or None)
                result["result"] = {"total": len(data), "results": data}
            elif intent == "reverse" and tid:
                data = cls.reverse_match(db, tid, top_k=10)
                result["result"] = {"total": len(data), "results": data}
            elif intent == "explain":
                data = cls._resolve_explain(db, pid=pid, tid=tid)
                result["result"] = data
            else:
                intent = "unknown"
                result["intent"] = intent
        except BusinessError as e:
            result["error"] = str(e.detail if hasattr(e, "detail") else e)
            intent = "unknown"

        # 4. LLM 生成自然语言回复（失败降级规则化文案）
        result["reply"] = cls._make_reply(llm, intent, parsed, result.get("result"), result.get("error"))
        return result

    @classmethod
    def _nlp_parse(cls, db: Session, message: str) -> dict[str, Any]:
        """LLM 意图识别 + 参数抽取。失败时规则化兜底。"""
        prompt = (
            "你是岗位匹配助手。解析用户自然语言指令，输出**纯 JSON**（不要 markdown 代码块）：\n"
            '{"intent":"parse|match|reverse|explain|unknown","position":"岗位名称或null",'
            '"talent":"人才姓名/ID或null","filters":{"degree":"学历要求或null","years":经验年限数字或null,'
            '"skills":["必备技能数组或[]"]}}\n'
            "意图判断：解析岗位要求→parse；给岗位找人才→match；给人才找岗位→reverse；"
            "问匹配原因/为什么排第几→explain；无法判断→unknown。\n"
            "注意：filters 只从用户明确提出的条件中提取，没有就填 null/空。\n"
            f"用户指令：{message}"
        )
        try:
            from app.utils.llm import get_llm

            raw = get_llm().chat(prompt, system="只输出合法 JSON。")
            parsed = cls._extract_json(raw)
            if parsed:
                return {
                    "intent": parsed.get("intent", "unknown"),
                    "position": parsed.get("position"),
                    "talent": parsed.get("talent"),
                    "filters": parsed.get("filters") or {},
                }
        except Exception:  # noqa: BLE001
            pass
        return cls._rule_based_nlp(message)

    @classmethod
    def _rule_based_nlp(cls, message: str) -> dict[str, Any]:
        """规则化兜底意图判断（LLM 不可用时）。"""
        msg = message or ""
        filters: dict[str, Any] = {"degree": None, "years": None, "skills": []}
        m = re.search(r"(\d+)\s*年", msg)
        if m:
            filters["years"] = int(m.group(1))
        for d in ("博士", "硕士", "本科", "大专"):
            if d in msg:
                filters["degree"] = d
                break
        if "岗位" in msg and ("要求" in msg or "分析" in msg or "解析" in msg):
            return {"intent": "parse", "position": None, "talent": None, "filters": filters}
        if "适合" in msg and ("人才" in msg or "谁" in msg):
            return {"intent": "match", "position": None, "talent": None, "filters": filters}
        if "岗位" in msg and "人才" in msg:
            return {"intent": "reverse", "position": None, "talent": None, "filters": filters}
        if "为什么" in msg or "依据" in msg:
            return {"intent": "explain", "position": None, "talent": None, "filters": filters}
        return {"intent": "unknown", "position": None, "talent": None, "filters": filters}

    @classmethod
    def _resolve_position(cls, db: Session, name: str | None) -> dict[str, Any] | None:
        """岗位名 → 记录（模糊匹配 name/code）。"""
        if not name:
            return None
        from sqlalchemy import text as sa_text

        key = str(name).strip()
        row = db.execute(
            sa_text("SELECT id, name FROM pos_position WHERE name = :k OR code = :k LIMIT 1"),
            {"k": key},
        ).mappings().first()
        if row:
            return dict(row)
        # 模糊包含匹配
        row = db.execute(
            sa_text("SELECT id, name FROM pos_position WHERE :k LIKE CONCAT('%', name, '%') "
                    "OR name LIKE CONCAT('%', :k, '%') LIMIT 1"),
            {"k": key},
        ).mappings().first()
        return dict(row) if row else None

    @classmethod
    def _resolve_talent(cls, db: Session, ref: str | int | None) -> dict[str, Any] | None:
        """人才姓名/ID → 记录。"""
        if ref is None:
            return None
        from sqlalchemy import text as sa_text

        try:
            tid = int(str(ref).strip())
        except (TypeError, ValueError):
            # 兼容 "人才5" / "人才#5" / "人才：5" 格式 → id=5
            m = re.search(r"人才\s*[:：#]?\s*(\d+)", str(ref))
            tid = int(m.group(1)) if m else 0
        if tid > 0:
            row = db.execute(
                sa_text("SELECT id, name FROM tal_talent WHERE id = :i LIMIT 1"), {"i": tid},
            ).mappings().first()
            if row:
                return dict(row)
        row = db.execute(
            sa_text("SELECT id, name FROM tal_talent WHERE name LIKE :n LIMIT 1"),
            {"n": f"%{str(ref).strip()}%"},
        ).mappings().first()
        return dict(row) if row else None

    @classmethod
    def _resolve_explain(cls, db: Session, *, pid: int | None, tid: int | None) -> dict[str, Any] | None:
        """解析匹配依据：优先 (talent_id, position_id) 组合，否则该人才/岗位最新记录。"""
        from app.models.matching import MatchResult

        rec = None
        if tid and pid:
            rec = MatchResultDAO.get_by_pair(db, tid, pid)
        if not rec and tid:
            rec = db.query(MatchResult).filter(MatchResult.talent_id == tid).order_by(MatchResult.id.desc()).first()
        if not rec and pid:
            rec = db.query(MatchResult).filter(MatchResult.position_id == pid).order_by(MatchResult.id.desc()).first()
        if not rec:
            return None
        explain = MatchingService.explain(db, rec.id, force=False)
        return {
            "match_id": rec.id, "talent_id": rec.talent_id, "position_id": rec.position_id,
            "score": float(rec.score), "dimension_json": rec.dimension_json, "explain": explain,
        }

    @staticmethod
    def _make_reply(llm, intent: str, params: dict[str, Any], result, error: str | None) -> str:
        """生成自然语言回复：LLM 总结，失败降级规则化文案。"""
        if error:
            return f"抱歉，执行失败：{error}"
        try:
            if intent == "parse" and result:
                return llm.chat(
                    f"岗位「{result.get('title','')}」解析结果：技能标准{result.get('skill_standards',[])}，"
                    f"学历要求{result.get('degree_threshold','不限')}，经验要求"
                    f"{result.get('experience_threshold',{}).get('text','不限')}，核心要求{result.get('core_requirements',[])[:2]}。"
                    "请用 60 字以内中文总结这段岗位解析结果。",
                    system="你是岗位分析助手，输出简洁自然。",
                )
            if intent == "match" and result and result.get("results"):
                top = result["results"][0]
                return llm.chat(
                    f"匹配岗位共{result['total']}名候选。第1名人才#{top['talent_id']}得分{top['score']}。"
                    "请用 60 字以内中文告知用户匹配完成情况并推荐第1名。",
                    system="你是 HR 招聘助手，输出简洁自然。",
                )
            if intent == "reverse" and result and result.get("results"):
                top = result["results"][0]
                return llm.chat(
                    f"该人才适配{result['total']}个岗位，最适配「{top['position_name']}」得分{top['score']}。"
                    "请用 50 字以内中文告知用户。",
                    system="你是 HR 招聘助手，输出简洁自然。",
                )
            if intent == "explain" and result:
                return f"匹配依据：{result['explain']}"
        except Exception:  # noqa: BLE001
            pass
        # 降级规则化
        if intent == "parse" and result:
            return (f"岗位「{result.get('title','')}」要求：学历{result.get('degree_threshold','不限')}、"
                    f"经验{result.get('experience_threshold',{}).get('text','不限')}，"
                    f"技能标准{result.get('skill_standards',[])}。")
        if intent == "match" and result and result.get("results"):
            top = result["results"][0]
            return f"共匹配出 {result['total']} 名候选，第1名是人才#{top['talent_id']}（{top['score']}分）。"
        if intent == "reverse" and result and result.get("results"):
            top = result["results"][0]
            return f"最适配岗位：「{top['position_name']}」（{top['score']}分），共 {result['total']} 个适配岗位。"
        if intent == "explain" and result:
            return f"匹配依据：{result['explain']}"
        return ("我是岗位人才匹配助手，可以这样问我：\n"
                "· 「分析XX岗位的要求」→ 解析岗位需求\n"
                "· 「找适合XX岗位的人才，硕士、3年经验、会Python」→ 匹配人才\n"
                "· 「人才5适合什么岗位」→ 反向匹配\n"
                "· 「为什么人才7排第一」→ 匹配依据解释")
