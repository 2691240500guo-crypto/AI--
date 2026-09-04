"""岗位人才匹配 Agent（M 域核心 AI 能力）。

职责（对齐《AI岗位人才智能匹配模块》需求）：
1. 岗位智能解析：LLM 拆解岗位任职要求/技能标准/经验门槛/学历要求/综合素质 → 标准化标签体系
2. 双向精准匹配：岗位→人才（run_match）、人才→岗位（reverse_match），0-100 分
3. 双重策略打分：硬性条件过滤（学历/经验/必备技能）+ 软性能力加权（skill/degree/years/quality）
4. 候选人才排序 + 匹配原因解释（复用 MatchingService.explain）

AI 底座：硅基流动 Qwen3-30B（chat）+ bge-m3（embed，1024 维）+ Milvus（人才四维集合/position_vec）。

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
# 人才向量统一读四维集合中的 resume 维（2026-09-03 收敛：批处理 talent_vec 已退役）。
# resume 文本带【人才id|学历|经验|技能】meta 头 + 简历原文，由 upsert_talent_vectors 实时写入，
# 增改档案即可命中，无需再手动运行 vectorize 批处理。
TALENT_VEC_COLLECTION = "resume"

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

        result = {
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
        # 需求1：标签体系落库持久化，支持重查与追溯
        try:
            p.parsed_json = json.dumps(result, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            p.parsed_json = None
        db.commit()
        return result

    @classmethod
    def parse_jd(cls, db: Session, text: str, *, position_id: int | None = None,
                 title_hint: str | None = None) -> dict[str, Any]:
        """自由文本岗位需求/岗位说明书解析（需求1：手动录入/导入 JD → 标准化岗位需求标签）。

        与 parse_requirement 的区别：不要求该岗位已建档，直接把用户粘贴的需求文本/说明书
        拆解为 核心要求/技能标准/经验门槛/学历/综合素质/标签。position_id 存在时结果同步落库。
        """
        body = (text or "").strip()
        if not body:
            raise BusinessError(400, "未提供岗位需求/说明书文本")
        pname = title_hint or ""
        pid = None
        if position_id:
            p = PosPositionDAO.get(db, position_id)
            if p:
                pname = pname or p.name
                pid = p.id
                if p.description:
                    body = f"{pname}\n{p.description}" if pname not in body else body
        if not pname:
            pname = "自定义岗位需求"

        prompt = (
            "你是资深岗位分析师。请把用户粘贴的岗位需求/岗位说明书拆解成标准化标签体系，"
            "输出**纯 JSON**（不要 markdown 代码块），格式：\n"
            '{"position_name":"岗位名称（从文本推断，推断不出则 null）",'
            '"core_requirements":["核心职责/要求，2-4条"],"skill_standards":["技能标准，如 Python"],'
            '"experience_threshold":{"years":3,"text":"3年以上"},"degree_threshold":"本科",'
            '"quality_dimensions":["综合素质维度，2-3个"],"tags":["标准化标签，5-10个"]}\n'
            "注意：经验年限用数字；学历阈值用 博士/硕士/本科/大专/不限；信息不足的字段填空值。\n"
            f"岗位名称（已知）：{pname}\n岗位需求/说明书文本：\n{body[:3000]}"
        )
        parsed: dict[str, Any] | None = None
        try:
            from app.utils.llm import get_llm
            raw = get_llm().chat(prompt, system="只输出合法 JSON，不要任何解释文字。")
            parsed = cls._extract_json(raw)
        except Exception:  # noqa: BLE001
            parsed = None

        if not parsed:
            # LLM 不可用 → 规则化兜底（复用岗位解析规则，用轻量命名空间对象）
            class _P:  # noqa: D106
                name = pname
                code = ""
                description = body
            parsed = cls._rule_based_parse(_P())

        llm_name = str(parsed.get("position_name") or "").strip()
        result = {
            "position_id": pid,
            "title": llm_name or pname,
            "code": "",
            "source": "free-text" if pid is None else "position",
            "core_requirements": parsed.get("core_requirements", []),
            "skill_standards": parsed.get("skill_standards", []),
            "experience_threshold": parsed.get("experience_threshold", {"years": 0, "text": "不限"}),
            "degree_threshold": parsed.get("degree_threshold", "不限"),
            "quality_dimensions": parsed.get("quality_dimensions", []),
            "tags": parsed.get("tags", []),
        }
        if pid:
            try:
                p.parsed_json = json.dumps(result, ensure_ascii=False)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
        return result

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
        """经验维度：达标 90，超出加分（封顶 100），不足按差额 15/年 递减（最低 20）。

        精度优化 2026-09-02：扣分斜率 10→15、下限 30→20，把"差一年"的人才明显刷低，
        避免仅凭年限优势挤进前排。
        """
        if not require_years:
            return 75.0
        if talent_years <= 0:
            return 65.0
        if talent_years >= require_years:
            return min(100.0, 90.0 + (talent_years - require_years) * 5)
        return max(20.0, 90.0 - (require_years - talent_years) * 15)

    @classmethod
    def _skill_score(cls, talent_skills: list[str], skill_standards: list[str],
                     similarity: float) -> float:
        """技能维度：向量相似度×0.3 + 技能标准命中率×0.7 → 0-100。

        精度优化 2026-09-02：
        - 关键词命中权重提到 0.7，语义相似降到 0.3（压制"语义像但技能对不上"的假阳性）
        - 零命中不再吃 30 分兜底，只保留 0.3×sim（≤30），与有命中明显拉开差距
        """
        sim_score = min(100.0, similarity * 100)
        if not skill_standards:
            return round(sim_score, 2)
        low = [s.lower() for s in talent_skills]
        covered = [s for s in skill_standards if any(s.lower() in t or t in s.lower() for t in low)]
        if not covered:
            # 零命中：保留少量语义分即可，避免假阳性挤进 top_k
            return round(sim_score * 0.3, 2)
        coverage = len(covered) / len(skill_standards)
        hit_score = min(100.0, 40.0 + coverage * 60.0)
        return round(sim_score * 0.3 + hit_score * 0.7, 2)

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
            raise BusinessError(400, "人才画像向量未就绪：请先创建/更新人才档案触发画像向量化（或执行 scripts/vectorize_talents.py 回灌存量）")

        # 2. 岗位向量 → Milvus 高维语义检索
        qvec = llm.embed(MatchingService.build_profile_text(p))
        hits = vec.search(TALENT_VEC_COLLECTION, qvec, top_k=top_k * 3)

        # 3. 硬过滤 + 4. 软加权 + 5. 排序
        results: list[dict[str, Any]] = []
        for h in hits:
            talent_text = h.get("text", "")
            similarity = float(h.get("score", 0.0))
            meta = cls._parse_talent_meta(talent_text)
            if meta["talent_id"] <= 0:
                # 历史脏向量缺少【人才id】标记，无法关联人才 → 跳过（勿用 Milvus id 冒充人才 id）
                continue
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

        # 批量附加人才基础信息（T 域 tal_talent 只读复用，供前端卡片/表格展示）
        if results:
            tids = [r["talent_id"] for r in results]
            from sqlalchemy import text as sa_text

            rows = db.execute(
                sa_text("SELECT id,name,avatar,current_title,current_company,degree,"
                        "years_experience,skills FROM tal_talent WHERE id IN :ids"),
                {"ids": tuple(tids)},
            ).mappings().all()
            tinfo = {r["id"]: dict(r) for r in rows}
            for m in results:
                info = tinfo.get(m["talent_id"], {})
                m["talent_name"] = info.get("name") or f"人才{m['talent_id']}"
                m["avatar"] = info.get("avatar")
                m["current_title"] = info.get("current_title")
                m["current_company"] = info.get("current_company")
                m["degree"] = m.get("degree") or info.get("degree") or ""
                m["years"] = m.get("years") or (info.get("years_experience") or 0)

        # 6. 落库 match_result（幂等，已推荐/录用不覆盖）
        # 先按 status!=0 过滤，再对可见列表连续编号 1..N，避免跳过造成的 rank=2/3 与"第一名"不一致
        visible: list[dict[str, Any]] = []
        for m in results:
            rec = MatchResultDAO.get_by_pair(db, m["talent_id"], m["position_id"])
            if rec and rec.status != 0:
                continue  # 已推荐/录用结论保留
            visible.append((m, rec))
        saved: list[dict[str, Any]] = []
        for rank, (m, rec) in enumerate(visible, start=1):
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
                "talent_name": m.get("talent_name", f"人才{m['talent_id']}"),
                "avatar": m.get("avatar"),
                "current_title": m.get("current_title"),
                "current_company": m.get("current_company"),
                "degree": m.get("degree", ""),
                "years": m.get("years", 0),
                "skills": m.get("skills", []),
                "status": rec.status,
            }
            # 解释生成（仅 Top3 生成 LLM 解释避免全量卡顿；LLM 失败自动降级规则化）
            if gen_explain and rank <= 3:
                try:
                    item["explain"] = MatchingService.explain(db, rec.id, force=False)
                except Exception:  # noqa: BLE001
                    item["explain"] = ""
            else:
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
        # hq+ 2026-09-04：脚本批量向量化 / UI 反复点击会产生同一岗位的多条向量，
        # 不去重的话，top_k*2 的召回窗口会被同岗位占据，真实岗位挤不进 top-N。
        seen_pids: set[int] = set()
        for h in hits:
            ptext = h.get("text", "")
            similarity = float(h.get("score", 0.0))
            pid_m = re.search(r"【岗位id[:：](\d+)", ptext)
            pid = int(pid_m.group(1)) if pid_m else 0
            if pid <= 0:
                continue
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            p = PosPositionDAO.get(db, pid)
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
        results = [r for r in results if r["score"] >= min_score][:top_k]

        # 去重：position_vec 同一岗位可能有多条重复向量，导致同一 position_id 多次进入 results；
        # 按 position_id 去重（保留最高分），否则落库时 UNIQUE(talent_id,position_id) 第二次 insert 会抛
        # IntegrityError（前端表现为"Internal server error" 500）。
        dedup: dict[int, dict[str, Any]] = {}
        for r in results:
            pid = r["position_id"]
            if pid not in dedup or r["score"] > dedup[pid]["score"]:
                dedup[pid] = r
        results = list(dedup.values())

        # 落库 match_result（幂等，与 run_match 一致；已推荐/录用结论不覆盖）
        # 先过滤 status!=0，再连续编号 1..N（与 run_match 同修复，避免 rank 与显示不一致）
        visible: list[tuple[dict[str, Any], Any]] = []
        for m in results:
            rec = MatchResultDAO.get_by_pair(db, talent_id, m["position_id"])
            if rec and rec.status != 0:
                continue
            visible.append((m, rec))
        saved: list[dict[str, Any]] = []
        for rank, (m, rec) in enumerate(visible, start=1):
            if rec:
                rec.score = m["score"]
                rec.dimension_json = m["dimension_json"]
                rec.rank = rank
                rec.status = 0
            else:
                rec = MatchResultDAO.create(
                    db, talent_id=talent_id, position_id=m["position_id"],
                    score=m["score"], dimension_json=m["dimension_json"],
                    rank=rank, status=0,
                )
            db.flush()
            item = {**m, "match_id": rec.id, "rank": rank, "status": rec.status,
                    "talent_id": talent_id}
            saved.append(item)
        db.commit()
        return saved

    # ==================== 自由文本需求 → 解析 + 匹配（小程序 Agent 契约） ====================

    @classmethod
    def _parse_query_text(cls, text: str) -> dict[str, Any]:
        """解析自由文本招聘/匹配需求 → 需求标签（LLM 拆解 + 规则兜底）。

        返回结构对齐小程序 Agent 页期望（miniapp agent.vue）：
            {core_duties[], required_skills[], bonus_skills[], min_education, min_years, soft_quality[]}
        """
        prompt = (
            "你是岗位分析师。请把用户的招聘/匹配需求文本拆解成结构化 JSON（纯 JSON，不要代码块）：\n"
            '{"core_duties":["核心职责/定位，1-3条"],"required_skills":["必备技能"],'
            '"bonus_skills":["加分技能"],"min_education":"本科|硕士|博士|大专|不限",'
            '"min_years":经验年限数字,"soft_quality":["软性素质/综合要求"]}\n'
            "信息不足的字段填空值：技能/职责/素质填空数组，学历填 不限，年限填 0。\n"
            f"需求文本：{text}"
        )
        parsed: dict[str, Any] | None = None
        try:
            from app.utils.llm import get_llm

            raw = get_llm().chat(prompt, system="只输出合法 JSON，不要解释文字。")
            parsed = cls._extract_json(raw)
        except Exception:  # noqa: BLE001
            parsed = None

        if not parsed:
            parsed = cls._rule_parse_query_text(text)  # LLM 失败 → 规则兜底

        min_education = parsed.get("min_education") or ""
        if min_education in ("不限", "未知", "无"):
            min_education = ""  # 空串=无学历门槛：过滤时放行、前端不显示"不限学历"

        return {
            "core_duties": parsed.get("core_duties") or [],
            "required_skills": parsed.get("required_skills") or [],
            "bonus_skills": parsed.get("bonus_skills") or [],
            "min_education": min_education,
            "min_years": int(parsed.get("min_years") or 0),
            "soft_quality": parsed.get("soft_quality") or [],
        }

    @staticmethod
    def _rule_parse_query_text(text: str) -> dict[str, Any]:
        """规则化兜底：从需求文本抽取 学历/年限/技能 关键词。"""
        msg = text or ""
        years = 0
        m = re.search(r"(\d+)\s*年", msg)
        if m:
            years = int(m.group(1))
        degree = "不限"
        for d in ("博士", "硕士", "本科", "大专"):
            if d in msg:
                degree = d
                break
        stop = {"一个", "招聘", "招一个", "找一个", "找", "以及", "或者", "优先", "经验", "学历",
                "以上", "以下", "左右", "要求", "精通", "熟悉", "了解", "掌握", "会", "负责", "的",
                "人才", "人员", "岗位", "职位", "类型", "不限", "年以上", "年左右", "以下经验",
                "本科", "硕士", "博士", "大专", "年", "年经验"}
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fa5]{2,6}", msg)
        skills: list[str] = []
        for w in words:
            w = w.strip()
            if w in stop or len(w) <= 1:
                continue
            # 去尾巴噪音：如 "后端经验" -> 后端、"算法工程师" 整词保留、去掉截断的残缺词
            for suf in ("经验", "学历", "的人才", "年以上", "年左右", "工程师以上"):
                if w.endswith(suf) and len(w) > len(suf):
                    w = w[: -len(suf)]
                    break
            # "高级前端工程" 这类 findall 截断词（以"工程"结尾但原意是"工程师"）→ 保留"工程师"前缀部分
            if w.endswith("工程") and len(w) >= 3:
                w = w[:-2]
            # 去掉“会/找/招/有/及/或/与”等介词残留
            for pre in ("会", "招", "找", "及", "与"):
                if w.startswith(pre) and len(w) > 1:
                    w = w[len(pre):]
                    break
            if w and w not in stop and w not in skills:
                skills.append(w)
        return {
            "core_duties": [msg[:60]] if msg.strip() else [],
            "required_skills": skills[:10],
            "bonus_skills": [],
            "min_education": degree,
            "min_years": years,
            "soft_quality": [],
        }

    @classmethod
    def query_match(cls, db: Session, query_text: str, *, top_k: int = 10,
                    min_score: float = 0.0) -> dict[str, Any]:
        """自由文本需求 → 需求标签 + 人才匹配（小程序 Agent 页调用）。

        流程：query_text 解析为需求标签 → 需求文本向量检索 talent_vec →
        硬过滤（学历/年限/技能）→ 软加权打分（skill/degree/years/quality）→ 排序返回（不落库）。
        返回结构与 miniapp agent.vue 契约一致：
            {query_requirement: {...标签}, results: [{talent_id, rank, score, dims, explain, ...}]}
        """
        text = (query_text or "").strip()
        if not text:
            raise BusinessError(400, "请输入招聘/匹配需求描述")

        req = cls._parse_query_text(text)  # 需求标签（LLM 拆解 + 规则兜底）

        from app.utils.llm import get_llm
        from app.utils.vector_store import get_vector_store

        try:
            llm, vec = get_llm(), get_vector_store()
        except Exception as e:  # noqa: BLE001
            raise BusinessError(500, f"AI 底座不可用：{e}") from e
        if not vec.has_collection(TALENT_VEC_COLLECTION):
            raise BusinessError(400, "人才画像向量未就绪：请先创建/更新人才档案触发画像向量化（或执行 scripts/vectorize_talents.py 回灌存量）")

        # 需求文本向量 → 检索人才
        qvec = llm.embed(text)
        hits = vec.search(TALENT_VEC_COLLECTION, qvec, top_k=top_k * 3)

        # 组装硬过滤条件（与 run_match 相同的 req 结构）
        filter_req = {
            "degree_threshold": req["min_education"] or "不限",
            "experience_threshold": {"years": req["min_years"], "text": f"{req['min_years']}年以上" if req["min_years"] else "不限"},
            "skill_standards": req["required_skills"],
            "mandatory_skills": None,
        }

        results: list[dict[str, Any]] = []
        for h in hits:
            talent_text = h.get("text", "")
            similarity = float(h.get("score", 0.0))
            meta = cls._parse_talent_meta(talent_text)
            if meta["talent_id"] <= 0:
                # 历史脏向量缺少【人才id】标记，无法关联人才 → 跳过
                continue
            ok_flag, _reason = cls._hard_filter(meta, filter_req)
            if not ok_flag:
                continue
            skill = cls._skill_score(meta["skills"], req["required_skills"], similarity)
            degree = cls._degree_score(meta.get("degree", ""), req["min_education"])
            years = cls._years_score(meta.get("years", 0), req["min_years"])
            quality = cls._quality_score(similarity, talent_text)
            dims = {"skill": skill, "degree": degree, "years": years, "quality": quality}
            total = round(min(100.0, sum(dims[k] * DEFAULT_RULE.get(k, 0) for k in dims)), 2)
            results.append({
                "talent_id": meta["talent_id"],
                "score": total,
                "dimension_json": json.dumps(dims, ensure_ascii=False),
                "talent_text": talent_text,
                "degree": meta.get("degree", ""),
                "years": meta.get("years", 0),
                "skills": meta.get("skills", []),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        results = [r for r in results if r["score"] >= min_score][:top_k]

        # 附加人才基础信息（T 域 tal_talent 只读复用）
        if results:
            tids = [r["talent_id"] for r in results]
            from sqlalchemy import text as sa_text

            rows = db.execute(
                sa_text("SELECT id,name,avatar,current_title,current_company FROM tal_talent WHERE id IN :ids"),
                {"ids": tuple(tids)},
            ).mappings().all()
            tinfo = {r["id"]: dict(r) for r in rows}
            for m in results:
                info = tinfo.get(m["talent_id"], {})
                m["talent_name"] = info.get("name") or f"人才{m['talent_id']}"
                m["avatar"] = info.get("avatar")
                m["current_title"] = info.get("current_title")
                m["current_company"] = info.get("current_company")
            # dims 对象化（小程序模板直接遍历）
            for m in results:
                dims = json.loads(m.pop("dimension_json") or "{}")
                m["dims"] = {k: float(dims.get(k, 0)) for k in dims}
                m.pop("talent_text", None)
                m["explain"] = cls._rule_explain(dims)  # 规则化解释（不调 LLM，保证小程序快速返回）

        # 排序名次
        for rank, m in enumerate(results, start=1):
            m["rank"] = rank

        return {"query_requirement": req, "total": len(results), "results": results}

    @staticmethod
    def _rule_explain(dims: dict) -> str:
        """按四维得分生成简短的规则化匹配解释（优势/短板）。"""
        labels = {"skill": "技能", "degree": "学历", "years": "经验", "quality": "综合素质"}
        items = [(labels.get(k, k), float(v)) for k, v in (dims or {}).items()]
        if not items:
            return ""
        items.sort(key=lambda kv: kv[1], reverse=True)
        best = items[0]
        worst = items[-1] if len(items) > 1 else None
        parts = [f"{best[0]}匹配最佳（{best[1]:.0f} 分）"]
        if worst and worst[1] < 70 and worst is not best:
            parts.append(f"{worst[0]}稍弱（{worst[1]:.0f} 分）")
        return "，".join(parts) + "。"

    # ==================== 智能筛选排序（需求3） ====================

    RANK_SORT_MAP = {
        "score": "match_result.score",
        "level": "CASE WHEN tal_talent.level IS NULL OR tal_talent.level = '' THEN '0' ELSE tal_talent.level END",
        "exp_years": "COALESCE(tal_talent.years_experience,0)",
        "quality_score": "COALESCE(tal_talent_report.composite_score,0)",
    }
    RANK_SORT_CN = {
        "score": "匹配度", "level": "能力等级", "exp_years": "从业经验", "quality_score": "综合评分",
    }

    @classmethod
    def rank_talents(cls, db: Session, *, position_id: int,
                     sort_by: str = "score", top_n: int = 5,
                     status: int | None = None, min_score: float | None = None,
                     keyword: str | None = None) -> dict[str, Any]:
        """智能筛选排序（需求3）：对某岗位已有匹配结果按 匹配度/能力等级/从业经验/综合评分 排序。

        读侧只读复用 T 域 tal_talent / tal_talent_report 做 JOIN，不落库。
        返回 {total, sort_by, rows:[{match_id, talent_id, talent_name, current_title, score, ...}]}
        """
        sort_key = (sort_by or "score").strip()
        if sort_key not in cls.RANK_SORT_MAP:
            sort_key = "score"
        if top_n < 1 or top_n > 50:
            top_n = 10
        from sqlalchemy import select as sa_select, and_, or_, text as sa_text
        from app.models.matching import MatchResult
        from app.models.talent import Talent
        from app.models.talent_report import TalentReport

        conds = [MatchResult.position_id == position_id]
        if status is not None:
            conds.append(MatchResult.status == status)
        if min_score is not None:
            conds.append(MatchResult.score >= min_score)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append(or_(Talent.name.like(kw), Talent.current_title.like(kw),
                             Talent.skills.like(kw)))
        order_expr = sa_text(f"{cls.RANK_SORT_MAP[sort_key]} DESC, match_result.score DESC, match_result.id DESC")
        stmt = (sa_select(MatchResult)
                .outerjoin(Talent, MatchResult.talent_id == Talent.id)
                .outerjoin(TalentReport, TalentReport.talent_id == Talent.id)
                .where(and_(*conds))
                .order_by(order_expr)
                .limit(top_n))
        mrs = db.scalars(stmt).all()
        tids = [mr.talent_id for mr in mrs]
        t_map: dict[int, Any] = {}
        r_map: dict[int, Any] = {}
        if tids:
            t_map = {x.id: x for x in db.scalars(
                sa_select(Talent).where(Talent.id.in_(tids))).all()}
            r_map = {x.talent_id: x for x in db.scalars(
                sa_select(TalentReport).where(TalentReport.talent_id.in_(tids))).all()}
        rows: list[dict[str, Any]] = []
        for mr in mrs:
            t = t_map.get(mr.talent_id)
            rep = r_map.get(mr.talent_id)
            rows.append({
                "match_id": mr.id,
                "talent_id": mr.talent_id,
                "talent_name": (t.name if t else None) or f"人才{mr.talent_id}",
                "current_title": t.current_title if t else None,
                "degree": (t.highest_education if t else None) or "学历未知",
                "level": t.level if t else None,
                "exp_years": t.years_experience if t else None,
                "quality_score": float(rep.composite_score) if rep and rep.composite_score is not None else None,
                "score": float(mr.score or 0),
                "dimension_json": mr.dimension_json,
                "status": mr.status,
                "warm_level": mr.warm_level,
            })
        return {"total": len(rows), "sort_by": sort_key, "sort_label": cls.RANK_SORT_CN.get(sort_key, sort_key),
                "rows": rows}

    # ==================== 一键查看人才档案/测评/履历（需求3） ====================

    @classmethod
    def talent_profile(cls, db: Session, talent_id: int) -> dict[str, Any]:
        """读人才完整档案 + AI 测评报告 + 履历要点（只读，不落库）。

        返回 {talent_id, name, base{...}, report{...}, resume_snippet}
        """
        from sqlalchemy import select as sa_select
        from app.models.talent import Talent
        from app.models.talent_report import TalentReport

        t = db.scalars(sa_select(Talent).where(Talent.id == talent_id)).first()
        if not t:
            raise BusinessError(404, f"人才不存在: talent_id={talent_id}")
        rep = db.scalars(sa_select(TalentReport).where(
            TalentReport.talent_id == talent_id).limit(1)).first()

        # 手机/邮箱脱敏
        def _mask_phone(p: str | None) -> str:
            p = (p or "").strip()
            return p if len(p) < 7 else f"{p[:3]}****{p[-4:]}"

        def _mask_email(e: str | None) -> str | None:
            e = (e or "").strip()
            if not e or "@" not in e:
                return e or None
            name, _, domain = e.partition("@")
            shown = name[:2] + "****" if len(name) > 2 else name + "****"
            return f"{shown}@{domain}"

        base = {
            "name": t.name,
            "gender": t.gender,
            "degree": t.highest_education,
            "school": getattr(t, "school", None),
            "major": getattr(t, "major", None),
            "years": t.years_experience,
            "current_title": t.current_title,
            "current_company": t.current_company,
            "level": getattr(t, "level", None),
            "skills": (t.skills or "")[:300],
            "phone_masked": _mask_phone(t.phone),
            "email_masked": _mask_email(t.email),
        }
        report = None
        if rep:
            def _jlist(v):
                try:
                    lst = json.loads(v or "[]")
                    return lst if isinstance(lst, list) else []
                except Exception:  # noqa: BLE001
                    return []
            report = {
                "ability_level": getattr(rep, "ability_level", None),
                "composite_score": rep.composite_score,
                "potential": getattr(rep, "potential", None),
                "experience_summary": getattr(rep, "experience_summary", None),
                "summary_report": (getattr(rep, "summary_report", None) or "")[:1200],
                "skills": _jlist(getattr(rep, "skills", None))[:15],
                "highlights": _jlist(getattr(rep, "highlights", None))[:5],
                "shortcomings": _jlist(getattr(rep, "shortcomings", None))[:3],
                "fit_positions": _jlist(getattr(rep, "fit_positions", None))[:5],
            }
        resume_snippet = (t.resume_text or "")[:800]
        return {"talent_id": talent_id, "name": t.name, "base": base, "report": report,
                "resume_snippet": resume_snippet}

    # ==================== 自然语言操作（NL → 意图 → 执行 → 回复） ====================

    @classmethod
    def chat(cls, db: Session, message: str) -> dict[str, Any]:
        """自然语言操作入口：意图识别 → 参数抽取 → 实体映射 → 执行 → 自然语言回复。

        支持意图：
        - parse         岗位需求智能解析（"分析XX岗位的要求"/直接粘贴岗位需求或说明书文本）
        - match         岗位→人才匹配（"找适合XX的人才，要求…"）
        - reverse       人才→岗位反向匹配（"人才X适合什么岗位"）
        - rank          智能筛选排序（"XX岗位按综合评分排前5"）
        - profile       一键查看人才档案/测评报告/履历（"看下张三的档案/测评/履历"）
        - explain       匹配依据解释（"为什么人才X排第一" / "人才X和岗位Y的匹配原因"）
        - chart         图表生成（"生成XX岗位的柱状图/折线图/饼图"）
        - update_status 状态修改（"把张三推荐到XX岗位"/"录用XX岗位的李四"）
        - unknown       无法理解 → 返回帮助文案
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

        # 2.5 岗位名规则兜底：LLM 未提取出岗位名时，从消息中按"XX岗位"模式提取（清洗动词前缀）
        if intent in ("match", "chart", "parse", "rank") and not pid:
            # 模式1：XX岗位 / XX职位
            m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9+#\- ]{1,20}?)岗位|([\u4e00-\u9fa5A-Za-z0-9+#\- ]{1,20}?)职位", message)
            if not m:
                # 模式2：适合/匹配/找 XX 人才/岗位
                m = re.search(r"(?:适合|匹配|找)\s*([\u4e00-\u9fa5A-Za-z0-9+#\- ]{1,16}?)(?:的)?(?:人才|岗位|人)", message)
            if not m:
                # 模式3：生成/画/看 XX 的 (折线|柱状|饼)图（chart 指令无"岗位"关键词时用）
                m = re.search(r"(?:生成|画|显示|看|帮我)\s*([\u4e00-\u9fa5A-Za-z0-9+#\- ]{1,20}?)(?:的)?(?:折线图|柱状图|柱形图|饼图|图)\b", message)
            if m:
                name = m.group(1).strip()
                for w in ("生成", "画一下", "显示", "查看", "看看", "分析", "解析", "帮我找", "帮我", "找", "适合", "匹配", "一下", "给", "的", "看看"):
                    name = name.replace(w, "")
                name = name.strip()
                if name:
                    pos2 = cls._resolve_position(db, name)
                    if pos2:
                        pid = pos2["id"]

        # 2.6 人才名规则兜底：profile/update_status/explain/reverse 缺人才实体时从"XX的档案/测评/履历"/"#ID" 等模式提取
        if intent in ("profile", "update_status", "explain", "reverse") and not tid:
            m = re.search(r"(?:看|查|查看|打开|展示|看看|把|将|录用|推荐|面试)?\s*([\u4e00-\u9fa5A-Za-z0-9]{1,6}?)(?:的)?(?:人才|档案|履历|测评|报告|简历|转|设为|标为|标记|到)", message)
            if not m:
                # 常见说法：人才ID #数字 / 陆一鸣#251 / 人才X
                m = re.search(r"(?:人才|#)\s*(\d+)", message)
            if m:
                ref = m.group(1).strip() if m.lastindex else message
                try:
                    tid2 = int(ref)
                except (TypeError, ValueError):
                    tid2 = None
                t2 = cls._resolve_talent(db, tid2 if tid2 else ref)
                if t2:
                    tid = t2["id"]

        # 2.7 rank 附加参数兜底：排序键 / 条数（LLM 未给出时按用户关键词推断）
        sort_by = parsed.get("sort_by")
        top_n = parsed.get("top_n")
        if intent == "rank" or (intent in ("match", "reverse") and sort_by):
            if not sort_by:
                if any(k in message for k in ("综合评分", "综合分", "质量", "quality")):
                    sort_by = "quality_score"
                elif any(k in message for k in ("从业经验", "经验", "年限", "exp")):
                    sort_by = "exp_years"
                elif any(k in message for k in ("能力等级", "等级", "level")):
                    sort_by = "level"
                else:
                    sort_by = "score"
            if top_n is None:
                m = re.search(r"(?:前|前?(\d{1,2})名|top\s*(\d+)|limit\s*(\d+))", message, re.IGNORECASE)
                if m:
                    try:
                        top_n = int(next((g for g in m.groups() if g), "5"))
                    except ValueError:
                        top_n = 5
                else:
                    top_n = 5
            parsed["sort_by"] = sort_by
            parsed["top_n"] = top_n

        # 友好兜底：用户提到查看档案/测评/履历但没解析出人才 → 明确提示，避免回退到通用帮助
        if not tid and any(k in message for k in ("档案", "履历", "测评报告", "测评结果", "AI报告", "简历")):
            m = re.search(r"(?:看下|看看|查一下|查看|打开|展示|查)?\s*([\u4e00-\u9fa5A-Za-z0-9]{1,6})", message)
            who = m.group(1).strip() if m else "您说的人才"
            result["error"] = (
                f"未找到人才「{who}」，请检查姓名/编号是否正确，或先确认档案已入库。"
            )
            intent = "unknown"
            result["intent"] = intent

        # 2.75 关键词兜底覆盖：LLM 偶尔把 rank/parse/update_status 误判成 match/unknown，按消息关键字修正
        msg_lower = message or ""
        if intent != "rank":
            kw_rank = any(k in msg_lower for k in ("排前", "前N名", "前几", "top", "排序",
                                                    "按综合评分", "按综合分", "按从业经验",
                                                    "按能力等级", "按匹配度"))
            if kw_rank and ("岗位" in msg_lower or "候选人" in msg_lower):
                intent = "rank"
                parsed["intent"] = "rank"
        if intent not in ("update_status",):
            m_status = re.search(r"(?:设为|设置为|标记为|改为|把)([\u4e00-\u9fa5]{1,6})?.*?(推荐|录用|候选)", msg_lower)
            has_modify = any(k in msg_lower for k in ("设为", "标记", "把", "改为", "设置成", "设置为", "标为"))
            if m_status and has_modify:
                intent = "update_status"
                parsed["intent"] = "update_status"
        if intent not in ("parse",):
            if any(k in msg_lower for k in ("解析成标签", "智能解析岗位需求", "拆解岗位",
                                            "生成标准化岗位需求标签", "任职要求·技能·学历·年限·素质标签")):
                intent = "parse"
                parsed["intent"] = "parse"

        # 3. 按意图执行
        result: dict[str, Any] = {"intent": intent, "params": parsed, "result": None}
        try:
            if intent == "parse" and pid:
                data = cls.parse_requirement(db, pid)
                result["result"] = data
            elif intent == "parse" and not pid:
                # 需求1：自由文本岗位需求/说明书 → 标准化标签体系（不要求岗位已建档）
                data = cls.parse_jd(db, message, position_id=None,
                                    title_hint=(position["name"] if position else None))
                result["result"] = data
            elif intent == "rank" and pid:
                data = cls.rank_talents(db, position_id=pid, sort_by=sort_by,
                                        top_n=int(top_n or 5))
                result["result"] = data
                result["intent"] = "rank"
            elif intent == "rank" and not pid:
                result["error"] = "请指明岗位（如：后端开发工程师岗位按综合评分排前5）"
                intent = "unknown"
            elif intent == "profile" and tid:
                data = cls.talent_profile(db, tid)
                result["result"] = data
                result["intent"] = "profile"
            elif intent == "profile" and not tid:
                result["error"] = "请指明要看哪位人才（如：看下张三的档案/测评/履历）"
                intent = "unknown"
            elif intent in ("match", "chart") and pid:
                # chart 意图不需要逐条 LLM 解释（省 30-50 秒）；match 默认也不生成（前端按需点"匹配依据"按钮生成）
                do_explain = (intent == "match")
                data = cls.run_match(db, pid, top_k=10, gen_explain=do_explain, filters=filters or None)
                result["result"] = {"total": len(data), "results": data}
                if intent == "chart":
                    result["chart_type"] = parsed.get("chart_type") or "bar"
                    result["result"]["chart_type"] = result["chart_type"]
                    result["intent"] = "chart"
                else:
                    result["intent"] = "match"
            elif intent == "reverse":
                matched: list[dict[str, Any]] = []
                if tid:
                    t0 = cls._resolve_talent(db, tid)
                    if t0:
                        matched = [t0]
                else:
                    ref = (parsed.get("talent") or "").strip()
                    if not ref:
                        # 从消息提取姓名："张一鸣适合什么岗位" → 张一鸣
                        mref = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{1,8}?)(?:适合|适配|匹配).*?(?:岗位|职位)", message)
                        if mref:
                            ref = mref.group(1).strip()
                        else:
                            mseg = re.search(r"([\u4e00-\u9fa5]{2,8})", message)
                            if mseg:
                                ref = mseg.group(1).strip()
                    if ref:
                        # 支持重名：按姓名解析出全部人才（如多个"张一鸣"）
                        matched = cls._resolve_talents_by_name(db, ref)
                if not matched:
                    who = ((parsed.get("talent") or "").strip() or "您说的人")
                    result["error"] = (
                        f"未找到人才「{who}」，请检查姓名/编号是否正确，或先确认档案已入库。"
                    )
                    intent = "unknown"
                    result["intent"] = intent
                else:
                    # 同名多人逐个反向匹配，按岗位聚合保留最高分
                    best: dict[int, dict[str, Any]] = {}
                    for t in matched:
                        try:
                            rows = cls.reverse_match(db, t["id"], top_k=10)
                        except Exception:  # noqa: BLE001
                            continue
                        for r in rows:
                            pid = r.get("position_id")
                            if pid is None:
                                continue
                            if pid not in best or (r.get("score") or 0) > (best[pid].get("score") or 0):
                                best[pid] = {**r, "talent_id": t["id"], "talent_name": t["name"]}
                    data = list(best.values())
                    data.sort(key=lambda r: r.get("score") or 0, reverse=True)
                    result["result"] = {"total": len(data), "results": data}
            elif intent == "update_status":
                if not pid or not tid:
                    result["error"] = "请指明要修改状态的人才与岗位（例如：把人才#250设为推荐到后端开发工程师岗位）"
                    intent = "unknown"
                else:
                    target_status = parsed.get("target_status")
                    if target_status is None:
                        target_status = 1
                    from app.services.matching import MatchingService
                    data = MatchingService.update_status_by_pair(
                        db, position_id=pid, talent_id=tid,
                        status=int(target_status), note=parsed.get("note"),
                    )
                    result["result"] = data
                    result["intent"] = "update_status"
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
            '{"intent":"parse|match|reverse|explain|rank|profile|update_status|unknown",'
            '"position":"岗位名称或null","talent":"人才姓名/ID或null",'
            '"sort_by":"score|level|exp_years|quality_score 或 null","top_n":5或null,'
            '"target_status":0|1|2|null,"note":"备注或null",'
            '"filters":{"degree":"学历要求或null","years":经验年限数字或null,'
            '"skills":["必备技能数组或[]"]}}\n'
            "意图判断：\n"
            "- 粘贴一段岗位需求/说明书或分析XX岗位→parse；\n"
            "- 给岗位找人才→match；给人才找岗位→reverse；\n"
            "- 要求对某岗位候选人按标准排序/筛选（匹配度/能力等级/从业经验/综合评分）→rank"
            "（sort_by：匹配度→score、能力等级→level、从业经验→exp_years、综合评分→quality_score；top_n 给数量）；\n"
            "- 查看某人才档案/测评报告/履历/简历→profile；\n"
            "- 问匹配原因/为什么排第几→explain；\n"
            "- 把某人才改成推荐/录用/候选→update_status（target_status:1=推荐 2=录用 0=候选）；\n"
            "- 无法判断→unknown。\n"
            "注意：filters 只从用户明确提出的条件中提取，没有就填 null/空。\n"
            f"用户指令：{message}"
        )
        try:
            from app.utils.llm import get_llm

            raw = get_llm().chat(prompt, system="只输出合法 JSON。")
            parsed = cls._extract_json(raw)
            if parsed:
                # 交叉验证：消息含图表关键词时强制 chart 意图（LLM 偶尔漏判）
                kw_chart = ("柱状图" in message or "柱形图" in message or "折线图" in message
                            or "饼图" in message or "bar" in message.lower()
                            or "line" in message.lower() or "pie" in message.lower())
                if kw_chart:
                    ct = parsed.get("chart_type")
                    if ct not in ("bar", "line", "pie"):
                        if "柱" in message or "bar" in message.lower():
                            ct = "bar"
                        elif "折" in message or "线图" in message or "line" in message.lower():
                            ct = "line"
                        else:
                            ct = "pie"
                    parsed["intent"] = "chart"
                    parsed["chart_type"] = ct
                intent = parsed.get("intent", "unknown")
                # 意图-实体一致性修正：match/chart/parse 无岗位实体、reverse 无人才实体时，
                # 若规则可识别则采用规则结果（LLM 不稳定兜底）
                if intent in ("match", "chart", "parse") and not parsed.get("position"):
                    rule = cls._rule_based_nlp(message)
                    if rule.get("intent") in ("match", "chart", "parse"):
                        rule["filters"] = parsed.get("filters") or rule.get("filters") or {}
                        return rule
                if intent == "reverse" and not parsed.get("talent"):
                    rule = cls._rule_based_nlp(message)
                    if rule.get("intent") in ("reverse", "match"):
                        return rule
                # LLM 判 unknown 时，若规则可识别则采用规则结果
                if intent == "unknown":
                    rule = cls._rule_based_nlp(message)
                    if rule.get("intent") != "unknown":
                        return rule
                return {
                    "intent": intent,
                    "position": parsed.get("position"),
                    "talent": parsed.get("talent"),
                    "chart_type": parsed.get("chart_type"),
                    "sort_by": parsed.get("sort_by"),
                    "top_n": parsed.get("top_n"),
                    "target_status": parsed.get("target_status"),
                    "note": parsed.get("note"),
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
        # 图表意图：柱状图→bar 折线图→line 饼图→pie
        chart_type = None
        if any(k in msg for k in ("柱状图", "柱形图", "bar")):
            chart_type = "bar"
        elif any(k in msg for k in ("折线图", "线图", "line")):
            chart_type = "line"
        elif any(k in msg for k in ("饼图", "pie")):
            chart_type = "pie"
        if chart_type and any(k in msg for k in ("生成", "画", "显示", "看", "图表", "柱状图", "折线图", "饼图")):
            return {"intent": "chart", "position": None, "talent": None,
                    "chart_type": chart_type, "filters": filters}
        if "岗位" in msg and ("要求" in msg or "分析" in msg or "解析" in msg):
            return {"intent": "parse", "position": None, "talent": None,
                    "chart_type": None, "filters": filters}
        # hq+ 2026-09-04：反向匹配兜底——「陆一鸣#251适合什么岗位」「人才251适配岗位」
        # 等说法不再要求消息里同时出现"岗位"和"人才"两个词（放 match 之前，避免误判）
        if any(k in msg for k in ("适合什么岗位", "适合哪些岗位", "适配什么岗位",
                                  "适配岗位", "适合岗位", "推荐岗位", "反向匹配")):
            return {"intent": "reverse", "position": None, "talent": None,
                    "chart_type": None, "filters": filters}
        if "岗位" in msg and "人才" in msg:
            return {"intent": "reverse", "position": None, "talent": None,
                    "chart_type": None, "filters": filters}
        # hq+ 2026-09-04：正向匹配兜底——「帮我找适合后端开发的人才」「招XX方向的人」
        if ("人才" in msg or "人" in msg) and any(k in msg for k in ("找", "招", "招聘", "匹配", "适合")):
            return {"intent": "match", "position": None, "talent": None,
                    "chart_type": None, "filters": filters}
        if "为什么" in msg or "依据" in msg:
            return {"intent": "explain", "position": None, "talent": None,
                    "chart_type": None, "filters": filters}
        # 智能筛选排序兜底：某岗位候选人 按 匹配度/能力等级/从业经验/综合评分 排序/筛前N
        kw_sort = any(k in msg for k in ("排序", "排名", "按", "筛", "前", "top", "综合评分",
                                         "综合分", "匹配度", "从业经验", "能力等级", "等级"))
        if kw_sort and ("岗位" in msg or "候选人" in msg or "前" in msg or "名" in msg):
            return {"intent": "rank", "position": None, "talent": None,
                    "chart_type": None, "sort_by": None, "top_n": None, "filters": filters}
        # 查看人才档案/测评/履历/简历兜底
        kw_view = any(k in msg for k in ("档案", "履历", "简历", "测评报告", "测评结果", "AI报告", "能力报告"))
        if kw_view and any(k in msg for k in ("看", "查", "打开", "展示", "给", "详情")):
            return {"intent": "profile", "position": None, "talent": None,
                    "chart_type": None, "sort_by": None, "top_n": None, "filters": filters}
        # 状态修改（自然语言兜底）：含 关键词 + 触发词
        target_status = None
        if "录用" in msg or "offer" in msg.lower() or "入职" in msg:
            target_status = 2
        elif "推荐" in msg or "面试" in msg or "推进" in msg:
            target_status = 1
        elif ("取消" in msg and "推荐" in msg) or "回到候选" in msg or "转为候选" in msg or "退回候选" in msg:
            target_status = 0
        kw_status = any(k in msg for k in ("推荐", "录用", "入职", "面试", "转为候选", "退回候选", "回到候选"))
        kw_modify = any(k in msg for k in ("改", "标记", "设为", "设置为", "把", "将", "调成"))
        if kw_status and (kw_modify or "改为" in msg or "设为" in msg or "标记为" in msg):
            return {"intent": "update_status", "position": None, "talent": None,
                    "chart_type": None, "target_status": target_status, "note": None,
                    "filters": filters}
        return {"intent": "unknown", "position": None, "talent": None,
                "chart_type": None, "filters": filters}

    @classmethod
    def _resolve_position(cls, db: Session, name: str | None) -> dict[str, Any] | None:
        """岗位名 → 记录（模糊匹配 name/code）。"""
        if not name:
            return None
        from sqlalchemy import text as sa_text

        key = str(name).strip()
        key2 = key.replace(" ", "")  # 去空格变体（兼容"AI 架构师"vs"AI架构师"）
        row = db.execute(
            sa_text("SELECT id, name FROM pos_position WHERE name = :k OR code = :k "
                    "OR REPLACE(name, ' ', '') = :k2 LIMIT 1"),
            {"k": key, "k2": key2},
        ).mappings().first()
        if row:
            return dict(row)
        # 模糊包含匹配（含去空格变体）
        row = db.execute(
            sa_text("SELECT id, name FROM pos_position WHERE :k LIKE CONCAT('%', name, '%') "
                    "OR name LIKE CONCAT('%', :k, '%') "
                    "OR REPLACE(name, ' ', '') LIKE CONCAT('%', :k2, '%') "
                    "OR :k2 LIKE CONCAT('%', REPLACE(name, ' ', ''), '%') LIMIT 1"),
            {"k": key, "k2": key2},
        ).mappings().first()
        return dict(row) if row else None

    @classmethod
    def _resolve_talent(cls, db: Session, ref: str | int | None) -> dict[str, Any] | None:
        """人才姓名/ID → 记录（取第一个匹配，单实体场景用）。"""
        if ref is None:
            return None
        from sqlalchemy import text as sa_text

        try:
            tid = int(str(ref).strip())
        except (TypeError, ValueError):
            # 兼容 "人才5" / "人才#5" / "人才：5" / "#5" / "5" → id=5
            m = re.search(r"(\d+)", str(ref))
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
    def _resolve_talents_by_name(cls, db: Session, name: str) -> list[dict[str, Any]]:
        """按姓名（模糊）解析出全部人才，支持重名多人（如多个"张一鸣"）。"""
        from sqlalchemy import text as sa_text

        key = str(name or "").strip()
        if not key:
            return []
        try:
            tid = int(key)
        except (TypeError, ValueError):
            tid = 0
        rows = db.execute(
            sa_text("SELECT id, name FROM tal_talent "
                    "WHERE id = :i2 OR (:i = 0 AND name LIKE :n) LIMIT 20"),
            {"i": tid, "i2": tid, "n": f"%{key}%"},
        ).mappings().all()
        return [dict(r) for r in rows]

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
        # —— 结构化结果可直接规则化回复（省 LLM 调用，结果更稳定） ——
        if intent == "update_status" and result:
            return (f"已将记录调整为「{result.get('status_label','未知')}」"
                    f"（match_id={result.get('match_id')}）。")
        if intent == "rank" and result and result.get("rows"):
            # hq+ 2026-09-04：rank 简化为一行短摘要，详细名单交给下方"智能筛选排序"表格，
            # 避免在 AI 气泡里再列一遍（与表格重复）
            rows = result["rows"]
            label = result.get("sort_label", "匹配度")
            return (f"已按【{label}】筛出 {len(rows)} 名候选人，详见下方「智能筛选排序」表格。")
        # 兼容旧路径：rank 但 result 缺失 rows 时降级列文字
        if intent == "rank":  # pragma: no cover - 兜底
            return "智能筛选排序已完成（详见下方表格）。"
        if intent == "profile" and result:
            b = result.get("base") or {}
            rep = result.get("report") or {}
            head = (f"{b.get('name') or ('人才#' + str(result.get('talent_id')))}｜"
                    f"{b.get('degree') or '学历未知'}·{(b.get('years') or 0)}年·{b.get('current_title') or '无职位'}·"
                    f"{b.get('current_company') or '—'}"
                    f"{'·等级' + str(b.get('level')) if b.get('level') else ''}")
            parts = [head]
            if rep:
                parts.append(f"测评：能力{rep.get('ability_level') or '未评'}｜综合分"
                             f"{rep.get('composite_score') or '—'}｜潜力{rep.get('potential') or '—'}")
                if rep.get("summary_report"):
                    parts.append("摘要：" + (rep["summary_report"] or "").replace("\n", "")[:90] + "…")
            if result.get("resume_snippet"):
                parts.append("履历要点：" + result["resume_snippet"].replace("\n", "")[:60] + "…")
            return "\n".join(parts)
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
            if intent == "chart" and result and result.get("results"):
                top = result["results"][0]
                ctype = {"bar": "柱状图", "line": "折线图", "pie": "饼图"}.get(
                    result.get("chart_type", "bar"), "柱状图")
                # chart 回复简单可规则化，直接返回（省 LLM 5-8 秒）
                return f"已生成{ctype}（{result['total']}名候选）。第1名：人才#{top['talent_id']}，{top['score']}分。"
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
        if intent == "chart" and result and result.get("results"):
            ctype = {"bar": "柱状图", "line": "折线图", "pie": "饼图"}.get(
                result.get("chart_type", "bar"), "柱状图")
            return f"已生成{ctype}（{result['total']}名候选）。第1名：人才#{result['results'][0]['talent_id']}，{result['results'][0]['score']}分。"
        return ("我是岗位人才匹配助手，可以这样问我（示例均用数据库真实岗位/人才）：\n"
                "· 「帮我把这段岗位需求解析成标签：负责 AI 产品规划，统招本科及以上，5年以上AI产品经验，熟悉大模型应用，具备跨团队协调能力」\n"
                "· 「分析后端开发工程师的岗位要求」\n"
                "· 「帮我找适合后端开发的人才，硕士、3年经验」\n"
                "· 「人才230适合什么岗位」\n"
                "· 「后端开发工程师岗位按综合评分排前5」\n"
                "· 「看下赵强的档案和测评报告」\n"
                "· 「把赵强设为推荐到后端开发工程师岗位」")
