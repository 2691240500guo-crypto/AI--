"""人才向量服务（批次 2.3c → 批次B 三维画像升级）。

批次B 按需求实现「向量级人才画像」：
    基于 Milvus 生成人才**技能向量 / 经验向量 / 素质向量**三个维度，
    每个维度一个集合（prefix 由基座加 talent_ 前缀）：
        talent_skill    技能向量   ← skills + summary 技术栈
        talent_exp      经验向量   ← 项目经历 / 亮点 / 适配岗位
        talent_quality  素质向量   ← 学历 / 潜力 / 短板（综合素质）

三个集合 schema 一致：id(talent_id 主键, auto_id=False) + vector + text。
用 talent_id 做主键天然幂等（重复 upsert 即覆盖），支持画像动态实时更新。

能力：
- ``upsert_talent_vectors(talent, report=None)``：三维一次性写入（动态更新入口）
- ``semantic_search_talents(query, top_k, dimension)``：按维度语义召回
- ``get_talent_vectors(talent_id)``：查看某人才三维向量（text 预览）
- 保留 ``upsert_talent_vector(talent)`` 兼容旧调用（只写技能维度，老接口不破坏）

依赖：
- pymilvus（基座 app/utils/vector_store.py 已就绪）
- Ollama + nomic-embed-text（基座 app/utils/llm.py 已就绪）

仅本模块新增。
"""
# hq新增内容 - 人才档案批次2.3c + 批次B
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from app.dao.talent import TalentDAO
from app.utils.llm import get_llm
from app.utils.vector_store import get_vector_store

logger = logging.getLogger(__name__)


# 四个维度集合名（基座自动加 MILVUS_COLLECTION_PREFIX=talent_）
# hq+ 2026-09-01：新增 resume 维（简历原文全文），语义搜索可直接按简历内容召回
DIMENSIONS = ["skill", "exp", "quality", "resume"]
DIM_LABEL = {"skill": "技能向量", "exp": "经验向量", "quality": "素质向量", "resume": "简历原文"}
# 详情页/编辑页仅展示三维（技能/经验/素质）；简历原文维度仅用于语义检索，不对外展示
DISPLAY_DIMS = ["skill", "exp", "quality"]

_EMBED_DIM: int | None = None  # 首次成功 embed 后缓存


def _ensure_collection(dimension: str) -> None:
    """懒创建某维度集合；schema：id(talent_id) + vector + text。"""
    global _EMBED_DIM
    vec = get_vector_store()
    if vec.has_collection(dimension):
        # hq+  集合已存在：确保有索引 + load（否则 search/query 报 index not found / not loaded）
        try:
            vec._client.load_collection(vec._name(dimension))
        except Exception as e:
            err_str = str(e)
            # hq+  连接断开（服务端 idle 超时）：reset 整个 client 重建连接
            if 'ConnectionNotExist' in err_str or 'should create connection' in err_str:
                logger.warning("[hq] Milvus 连接已断开（%s），重建客户端并重试", err_str[:80])
                try:
                    from app.utils.vector_store import _vector_store
                    _vector_store.__init__()  # 强制重连
                    vec = get_vector_store()
                except Exception as e1:
                    logger.warning("[hq] 重建 Milvus 客户端失败：%s", e1)
                try:
                    vec._client.load_collection(vec._name(dimension))
                    return
                except Exception:
                    pass
            # hq+  缺索引：补建
            logger.info("[hq] 集合 %s 加载失败（%s），尝试补建索引", dimension, err_str[:80])
            try:
                index_params = vec._client.prepare_index_params()
                index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="IP")
                vec._client.create_index(vec._name(dimension), index_params)
            except Exception as e2:
                logger.warning("[hq] 补建索引失败：%s", e2)
            try:
                vec._client.load_collection(vec._name(dimension))
            except Exception as e3:
                logger.warning("[hq] 补索引后仍无法 load：%s", e3)
        return
    if _EMBED_DIM is None:
        _EMBED_DIM = len(get_llm().embed("dim-probe"))
    from pymilvus import CollectionSchema, DataType, FieldSchema  # 惰性导入
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=_EMBED_DIM),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
    ]
    schema = CollectionSchema(fields=fields)
    client = vec._client
    client.create_collection(
        collection_name=vec._name(dimension),
        schema=schema,
        metric_type="IP",
    )
    # hq+  必须建向量索引，否则 load/search 报 "index not found"
    try:
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type="IP",
        )
        client.create_index(vec._name(dimension), index_params)
    except Exception as e:
        logger.warning("[hq] 建索引失败（可能已存在）：%s", e)
    try:
        client.load_collection(vec._name(dimension))
    except Exception:
        pass
    logger.info("[hq] 已创建 Milvus 集合：%s", vec._name(dimension))


# ============ 三维文本构建 ============
def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _split_main_skills(raw: str | None) -> list[str]:
    """把主档 skills 字符串（分号/逗号/顿号分隔）拆成干净技能词列表。

    用于调用方未传 report（report=None）时的技能兜底来源：
    主档 skills 是解析/编辑回写的技能短语，语义远好于简历原文截断。
    """
    if not raw:
        return []
    out: list[str] = []
    for part in re.split(r"[;；,，、]", str(raw)):
        p = part.strip()
        if p and p not in out:
            out.append(p)
    return out


def _build_dim_texts(talent, report=None) -> dict[str, str]:
    """从人才主档 + AI 报告构造四个维度的 embedding 文本（稳定可读）。

    :param report: TalentReport ORM（可空，缺省用主档字段兜底）
    """
    skills = _load_json_list(getattr(report, "skills", None)) if report else []
    highlights = _load_json_list(getattr(report, "highlights", None)) if report else []
    shortcomings = _load_json_list(getattr(report, "shortcomings", None)) if report else []
    fit = _load_json_list(getattr(report, "fit_positions", None)) if report else []
    potential = (report.potential if (report and report.potential) else "") or ""

    summary = (talent.summary or "")[:120]
    title = talent.current_title or ""
    company = talent.current_company or ""
    years = f"{talent.years_experience}年经验" if talent.years_experience else ""
    edu = talent.highest_education or ""

    # 1) 技能向量：优先 LLM 抽取技能（report.skills）→ 主档 skills → 摘要 → 语义兜底
    #    修复 hq+：原实现 skills 只从 report 读，调用方未传 report 时技能向量会
    #    降级成 resume_text[:100]（简历开头姓名电话，无技能语义）；现补主档 skills 兜底。
    skill_parts = list(skills) or _split_main_skills(talent.skills)
    if not skill_parts and summary:
        skill_parts = [summary]
    skill_text = "、".join(skill_parts) or _semantic_fallback(talent) or "(暂无技能信息)"

    # 2) 经验向量：项目经历 = 职称/公司/年限 + 亮点 + 适配岗位
    exp_parts = [title, company, years, *highlights, *fit]
    exp_text = "、".join(p for p in exp_parts if p) or _semantic_fallback(talent) or "(暂无经验信息)"

    # 3) 素质向量：综合素质 = 学历 + 潜力 + 短板提示
    quality_parts = [edu]
    if edu in ("硕士", "博士"):
        quality_parts.append("高学历")
    if potential:
        quality_parts.append(f"潜力评级{potential}")
    quality_parts.extend(shortcomings)
    quality_text = "、".join(p for p in quality_parts if p) or _semantic_fallback(talent) or "(暂无素质信息)"

    # 4) 简历原文向量：统一带双兼容头（match_agent 硬过滤解析）+ 简历原文（语义检索）
    #    头格式：【人才id:N|学历:X|经验:Y年|技能:Z】与 scripts 旧 talent_vec 同构，供
    #    MatchAgent._TALENT_META_RE 解析；写入端再统一加 talent_id=N|| 前缀供 _TID_RE 解析。
    body = (talent.resume_text or "").strip()[:1500]
    if not body:
        body = _main_body_text(talent)[:1500] or "(暂无简历内容)"
    resume_text = _meta_head(talent) + body

    return {
        "skill": skill_text,
        "exp": exp_text,
        "quality": quality_text,
        "resume": resume_text,
    }


def _meta_head(t) -> str:
    """结构化头（与 vectorize 脚本/匹配 Agent 契约同构）：【人才id:N|学历:X|经验:Y年|技能:Z】"""
    degree = (t.highest_education or "未知").strip()
    years = t.years_experience or 0
    try:
        years_num = int(float(str(years).strip()))
    except (TypeError, ValueError):
        years_num = 0
    skills = (t.skills or "").replace(";", ",").replace("；", ",")
    return f"【人才id:{int(t.id)}|学历:{degree}|经验:{years_num}年|技能:{skills}】"


def _main_body_text(t) -> str:
    """主档画像正文（无简历原文时的语义兜底，与 vectorize 脚本 build_talent_profile 同构）。"""
    parts = [f"姓名：{t.name or ''}"]
    if getattr(t, "major", None):
        parts.append(f"专业：{t.major}")
    if t.years_experience:
        parts.append(f"从业经验：{t.years_experience}")
    if t.current_title:
        parts.append(f"当前职称：{t.current_title}")
    if t.skills:
        parts.append(f"技能：{t.skills}")
    if t.work_experience:
        parts.append(f"工作经历：{t.work_experience}")
    if t.project_experience:
        parts.append(f"项目经历：{t.project_experience}")
    if t.honors:
        parts.append(f"荣誉：{t.honors}")
    if t.summary:
        parts.append(f"自我评价：{t.summary}")
    return "；".join(parts)


def _semantic_fallback(t) -> str:
    """技能/经验/素质结构化字段全空时的语义兜底（修复 hq+，替代原 resume_text[:100]）。

    原实现直接截简历开头 100 字 = 姓名/性别/电话等基本信息，几乎无技能/经历语义；
    现改为：
    1) 主档画像正文（技能/工作经历/项目经历等，语义好）；
    2) 仅简历原文时跳过开头基本信息区（前 100 字），取正文 100~700 字；
    3) 都没有 → 返回空串，由调用方标"暂无…"。
    """
    body = _main_body_text(t).strip()
    if body and body != f"姓名：{t.name or ''}":
        return body[:700]
    rt = (t.resume_text or "").strip()
    if rt:
        seg = rt[100:700].strip()
        if seg:
            return seg
        return rt[:300]
    return ""


# ============ 三维写入 / 动态更新 ============
def upsert_talent_vectors(talent, report=None) -> dict[str, int]:
    """把某人才的四维向量写进 Milvus（幂等 upsert，id=talent_id）。

    动态更新入口：talent 字段或 AI 报告变化后调用即可覆盖旧向量。
    返回 {dim: talent_id}，任一次失败不影响其它维度。
    hq+ 2026-09-01：text 统一为 talent_id=N||text 前缀（与袁文武 semantic_search
    _vector_search 的 _TAG_PREFIX_RE 解析兼容），语义搜索可按简历内容召回。
    """
    texts = _build_dim_texts(talent, report)
    vec = get_vector_store()
    ok_dims: dict[str, int] = {}
    for dim, text in texts.items():
        try:
            _ensure_collection(dim)
            emb = get_llm().embed(text)
            vec._client.upsert(
                collection_name=vec._name(dim),
                data=[{"id": int(talent.id), "vector": emb,
                       "text": f"talent_id={talent.id}||{text}"}],
            )
            ok_dims[dim] = int(talent.id)
        except Exception as e:  # pragma: no cover
            logger.warning("[hq] 维度 %s 向量化失败：%s", dim, e)
    return ok_dims


def upsert_talent_vector(talent, report=None) -> int | None:
    """兼容旧接口：只写技能维度（老调用方 vectorize 用）。"""
    result = upsert_talent_vectors(talent, report)
    return result.get("skill")


def get_talent_vectors(talent_id: int, talent=None) -> list[dict]:
    """查看某人才三维向量（text 预览）。返回 [{dim, label, text, has_vector}]。

    - 仅展示三维：技能/经验/素质（简历原文维度仅用于语义检索，不对外展示）。
    - Milvus 无该维度向量时，降级基于人才简历实时构造文本，保证详情页三维画像始终有内容。
    """
    vec = get_vector_store()
    # 无向量时的降级文本：基于人才主档字段实时构造
    fallback = _build_dim_texts(talent) if talent is not None else {}
    out: list[dict] = []
    for dim in DISPLAY_DIMS:
        item = {"dim": dim, "label": DIM_LABEL[dim], "text": None, "has_vector": False}
        try:
            if vec.has_collection(dim):
                # hq+  pymilvus 查询前必须 load 集合（auto_id=False 时不会自动 load）
                client = vec._client
                try:
                    client.load_collection(vec._name(dim))
                except Exception:
                    pass
                rows = client.query(
                    collection_name=vec._name(dim),
                    filter=f"id == {int(talent_id)}",
                    output_fields=["id", "text"],
                )
                if rows:
                    item["text"] = rows[0].get("text", "")
                    item["has_vector"] = True
        except Exception as e:  # pragma: no cover
            logger.warning("[hq] 查询维度 %s 失败：%s", dim, e)
        # 降级：Milvus 无该维度向量时，基于简历构造文本，保证画像有内容
        if not item["text"]:
            item["text"] = fallback.get(dim) or None
        out.append(item)
    return out


# ============ 语义搜索（按维度） ============
# hq+ 兼容两种 text 前缀：talent_id=N||（袁文武/新格式）与 N|（旧格式）
_TID_RE = re.compile(r"^(?:talent_id=)?(\d+)\|\|?")


def semantic_search_talents(query: str, top_k: int = 10, dimension: str = "skill") -> list[dict]:
    """自然语言 → 指定维度 Milvus 召回人才列表。

    :param dimension: skill/exp/quality
    """
    dim = dimension if dimension in DIMENSIONS else "skill"
    if not query.strip():
        return []
    try:
        _ensure_collection(dim)
    except Exception as e:
        logger.warning("[hq] 集合准备失败：%s", e)
        return []
    vec = get_vector_store()
    try:
        emb = get_llm().embed(query)
    except Exception as e:
        logger.warning("[hq] embedding 失败：%s", e)
        return []
    hits = vec.search(dim, emb, top_k=top_k)
    out: list[dict] = []
    for h in hits:
        text = h.get("text", "")
        m = _TID_RE.match(text)
        tid = int(m.group(1)) if m else None
        preview = text[m.end():] if m else text
        out.append({
            "talent_id": tid,
            "preview": preview,
            "score": float(h.get("score", 0.0)),
            "dimension": dim,
        })
    return out


# ============ 简化的「档案 RAG 问答」（基于 talent 主档字段直拼 prompt）============
RAG_QA_SYSTEM = """你是人才画像 AI 助手，专门根据候选人档案信息回答用户问题。请：
1. 严格基于给定资料回答，不要编造简历里没有的内容。
2. 回答简洁、有结构，必要时用要点列出。
3. 资料中查不到的字段请直接说「档案里未记录」。

资料格式：
{context}
"""


def answer_about_talent(db: Session, talent_id: int, question: str) -> str:
    """基于某人才的档案字段（包含 AI 报告）做问答。

    不是严格的向量召回，而是把候选人的摘要 + skills + highlights + shortcoming + report
    拼进 system prompt 直接问 LLM；对单一候选人最准确。
    """
    from app.dao.talent_report import TalentReportDAO  # 局部避免循环

    obj = TalentDAO.get(db, talent_id)
    if not obj:
        return "档案不存在"

    report = TalentReportDAO.get_by(db, talent_id=talent_id)
    skills = _load_json_list(report.skills) if report else []
    highlights = _load_json_list(report.highlights) if report else []
    shortcomings = _load_json_list(report.shortcomings) if report else []
    fit = _load_json_list(report.fit_positions) if report else []
    parts: list[str] = []
    if obj.name: parts.append(f"姓名：{obj.name}")
    if obj.current_title: parts.append(f"现职称：{obj.current_title}")
    if obj.current_company: parts.append(f"当前公司：{obj.current_company}")
    if obj.years_of_exp: parts.append(f"工作年限：{obj.years_of_exp} 年")
    if obj.education: parts.append(f"学历：{obj.education}")
    if obj.summary: parts.append(f"简介：{obj.summary}")
    if skills: parts.append("技能关键词：" + "、".join(skills))
    if highlights: parts.append("亮点：" + "、".join(highlights))
    if shortcomings: parts.append("短板：" + "、".join(shortcomings))
    if fit: parts.append("适配岗位：" + "、".join(fit))
    if report and report.summary_report: parts.append("评估总结：" + report.summary_report)
    context = "\n".join(parts) or "(档案为空)"

    system = RAG_QA_SYSTEM.format(context=context)
    from app.utils.llm import get_llm
    return get_llm().chat(question, system=system, temperature=0.3)
