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


def _build_dim_texts(talent, report=None) -> dict[str, str]:
    """从人才主档 + AI 报告构造三个维度的 embedding 文本（稳定可读）。

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

    # 1) 技能向量：LLM 抽的技能关键词 + 摘要技术栈
    skill_parts = list(skills)
    if not skill_parts and summary:
        skill_parts = [summary]
    skill_text = "、".join(skill_parts) or (talent.resume_text or "")[:100] or "(暂无技能信息)"

    # 2) 经验向量：项目经历 = 职称/公司/年限 + 亮点 + 适配岗位
    exp_parts = [title, company, years, *highlights, *fit]
    exp_text = "、".join(p for p in exp_parts if p) or (talent.resume_text or "")[:100] or "(暂无经验信息)"

    # 3) 素质向量：综合素质 = 学历 + 潜力 + 短板提示
    quality_parts = [edu]
    if edu in ("硕士", "博士"):
        quality_parts.append("高学历")
    if potential:
        quality_parts.append(f"潜力评级{potential}")
    quality_parts.extend(shortcomings)
    quality_text = "、".join(p for p in quality_parts if p) or "(暂无素质信息)"

    # 4) 简历原文向量（hq+ 2026-09-01）：用整篇简历文本做相似度搜索（截断控 token）
    resume_text = (talent.resume_text or "").strip()[:1500]
    if not resume_text:
        resume_text = (talent.summary or "")[:200] or (talent.skills or "")[:200] or "(暂无简历内容)"

    return {
        "skill": skill_text,
        "exp": exp_text,
        "quality": quality_text,
        "resume": resume_text,
    }


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


def get_talent_vectors(talent_id: int) -> list[dict]:
    """查看某人才三维向量（text 预览）。返回 [{dim, label, text, has_vector}]。"""
    vec = get_vector_store()
    out: list[dict] = []
    for dim in DIMENSIONS:
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
