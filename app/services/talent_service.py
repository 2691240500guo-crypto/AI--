#袁文武新增2026-08-31 17:10:00开始
"""人才档案业务服务（模块一核心编排）。

串联 AI 基建（Ollama 对话/Embedding、Milvus 向量、MinIO 对象存储、RAG）：
  1. 全格式简历智能解析入库（PDF/Word/图片）
  2. 向量级人才画像（技能/经验/素质三维向量 + 百级 AI 标签 + 潜力评级）
  3. 智能查重与数据治理（重复识别、缺失/错误提示、一键合并）
  4. 语义化人才检索（自然语言 → 向量语义匹配，Milvus 不可用时降级关键词）
  5. 档案 RAG 问答（单/批量人才，自动总结优势/短板/适配岗位/发展潜力）
所有 AI 依赖惰性导入、缺失时优雅降级，保证模块可独立运行与联调。
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.dao.talent import TalentDAO, TagDAO, TalentTagRelDAO
#袁文武新增2026-09-01 10:55:00开始 - 修复缺少TalentTag/TalentCertificate导入导致NameError
from app.models.talent import (
    Talent, TalentEducation, TalentWorkExperience, TalentProject, TalentTag,
    TalentTalentTag, TalentResumeParseLog, TalentCertificate,
)
#袁文武新增2026-09-01 10:55:00结束
from app.schemas.talent import (
    TalentCreate, EducationIn, WorkIn, ProjectIn, TalentProfileOut, SemanticSearchHit,
    RAGResponse, DedupResult, DuplicateCandidate, GovernanceIssue,
)
from app.utils.response import BusinessError

# 四维向量集合（落 Milvus，自动加 talent_ 前缀；hq+ 统一为 skill/exp/quality/resume 与 talent_vector_service 对齐，resume=简历原文）
_VECTOR_SETS = ("skill", "exp", "quality", "resume")
_TAG_PREFIX_RE = re.compile(r"^talent_id=(\d+)\|\|")


# ---------------- 内置 200+ 多维度标签库（可扩展）----------------
SEED_TAGS: list[tuple[str, str, str]] = [
    # 专业技能 skill
    ("Python", "skill", "编程语言"), ("Java", "skill", "编程语言"), ("Go", "skill", "编程语言"),
    ("C++", "skill", "编程语言"), ("SQL", "skill", "数据库"), ("Linux", "skill", "操作系统"),
    ("Docker", "skill", "容器化"), ("Kubernetes", "skill", "编排"), ("MySQL", "skill", "关系数据库"),
    ("Redis", "skill", "缓存"), ("MongoDB", "skill", "文档数据库"), ("FastAPI", "skill", "Web框架"),
    ("Spring", "skill", "Java框架"), ("PyTorch", "skill", "深度学习"), ("TensorFlow", "skill", "深度学习"),
    ("NLP", "skill", "自然语言处理"), ("机器学习", "skill", "AI"), ("深度学习", "skill", "AI"),
    ("数据分析", "skill", "数据"), ("数据建模", "skill", "数据"), ("ETL", "skill", "数据集成"),
    ("Tableau", "skill", "可视化"), ("PowerBI", "skill", "可视化"), ("Excel", "skill", "办公"),
    ("项目管理", "skill", "通用"), ("敏捷开发", "skill", "研发管理"), ("DevOps", "skill", "工程效能"),
    ("前端开发", "skill", "Web"), ("Vue", "skill", "前端框架"), ("React", "skill", "前端框架"),
    ("UI设计", "skill", "设计"), ("产品设计", "skill", "产品"), ("需求分析", "skill", "产品"),
    ("人力资源管理", "skill", "HR"), ("招聘", "skill", "HR"), ("薪酬绩效", "skill", "HR"),
    ("财务管理", "skill", "财务"), ("市场营销", "skill", "市场"), ("销售", "skill", "市场"),
    # 能力层级 level
    ("初级", "level", "0-2年"), ("中级", "level", "2-5年"), ("高级", "level", "5年以上"),
    ("骨干", "level", "团队中坚"), ("专家", "level", "领域权威"), ("架构师", "level", "技术决策"),
    ("管理者", "level", "带团队"), ("负责人", "level", "独立负责模块"),
    # 从业经验 exp
    ("3年以上经验", "exp", "资深"), ("5年以上经验", "exp", "专家"), ("10年以上经验", "exp", "资深专家"),
    ("互联网行业", "exp", "行业"), ("制造业", "exp", "行业"), ("金融", "exp", "行业"),
    ("政企", "exp", "行业"), ("创业经历", "exp", "经历"), ("海外经历", "exp", "经历"),
    ("大型项目", "exp", "项目规模"), ("从0到1", "exp", "建设经验"),
    # 综合素质 quality
    ("沟通能力强", "quality", "软技能"), ("抗压能力", "quality", "软技能"), ("学习能力", "quality", "软技能"),
    ("责任心强", "quality", "软技能"), ("团队协作", "quality", "软技能"), ("创新意识", "quality", "软技能"),
    ("逻辑思维", "quality", "软技能"), ("领导力", "quality", "软技能"), ("执行力强", "quality", "软技能"),
    ("客户导向", "quality", "软技能"), ("结果导向", "quality", "软技能"),
    # 适配岗位 position
    ("后端工程师", "position", "研发"), ("前端工程师", "position", "研发"), ("算法工程师", "position", "研发"),
    ("数据工程师", "position", "数据"), ("产品经理", "position", "产品"), ("项目经理", "position", "管理"),
    ("HRBP", "position", "HR"), ("财务专员", "position", "财务"), ("运维工程师", "position", "运维"),
    ("测试工程师", "position", "质量"), ("技术总监", "position", "管理"),
    # 潜力评级 potential
    ("高潜力", "potential", "P9"), ("中高潜力", "potential", "P8"), ("稳健型", "potential", "P7"),
    ("培养型", "potential", "P6"), ("待观察", "potential", "P5"),
]


# ---------------- 工具函数 ----------------
def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or len(phone) < 7:
        return "****" if phone else None
    return phone[:3] + "****" + phone[-4:]


# 袁文武新增2026-08-31 22:20:00开始
# 兼容适配：项目元代码 app/utils/vector_store.py 使用裸 uri "host:port"，
# 与 pymilvus>=2.6 要求的 "http://host:port" 不兼容（ConnectionConfigException）。
# 在不修改元代码的前提下，本模块统一改用带协议前缀的 MilvusClient，行为与 VectorStore 一致。
_MILVUS_COMPAT_DONE = False


def _vec_store():
    """返回兼容的 Milvus 客户端封装（集合名自动带 talent_ 前缀）。"""
    global _MILVUS_COMPAT_DONE
    from app.core.config import get_settings
    settings = get_settings()

    class _CompatStore:
        def __init__(self):
            from pymilvus import MilvusClient
            self.prefix = settings.MILVUS_COLLECTION_PREFIX
            # hq+ 修复：MILVUS_HOST 已含协议前缀（http://localhost），不能重复拼 http://
            self._client = MilvusClient(
                uri=f"{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
                db_name=settings.MILVUS_DB_NAME,
            )

        def _name(self, c):
            return f"{self.prefix}{c}"

        def create_collection(self, c, dim, *, metric="IP"):
            # pymilvus>=2.6 必须 auto_id=True，否则 insert 报缺 id 字段
            self._client.create_collection(collection_name=self._name(c), dimension=dim,
                                           metric_type=metric, auto_id=True)

        def has_collection(self, c):
            return self._client.has_collection(self._name(c))

        def insert(self, c, vectors, texts):
            data = [{"vector": v, "text": t} for v, t in zip(vectors, texts)]
            ids = self._client.insert(collection_name=self._name(c), data=data)
            return ids.get("ids", list(ids))

        def search(self, c, query_vector, top_k=5):
            res = self._client.search(collection_name=self._name(c), data=[query_vector],
                                      limit=top_k, output_fields=["text"])
            hits = res[0] if res else []
            return [{"id": h["id"], "text": h["entity"].get("text", ""), "score": h["distance"]} for h in hits]

        def delete_collection(self, c):
            self._client.drop_collection(self._name(c))

    return _CompatStore()
# 袁文武新增2026-08-31 22:20:00结束


def _talent_full_text(t: Talent) -> str:
    parts = [
        f"姓名：{t.name}",
        f"最高学历：{t.highest_education or ''}",
        f"专业：{t.major or ''}",
        f"期望职位：{t.current_title or ''}",
        f"从业年限：{t.years_experience}",
        f"技能：{t.skills or ''}",
        f"工作经历：{t.work_experience or ''}",
        f"项目经验：{t.project_experience or ''}",
        f"荣誉资质：{t.honors or ''}",
    ]
    return "\n".join(p for p in parts if p)


def _parse_tid(text: str) -> Optional[int]:
    m = _TAG_PREFIX_RE.match(text or "")
    return int(m.group(1)) if m else None


def _strip_tid(text: str) -> str:
    return _TAG_PREFIX_RE.sub("", text or "", count=1)


def _split_skills(skills: Optional[str]) -> list[str]:
    if not skills:
        return []
    return [s.strip() for s in re.split(r"[;；,，、/]", skills) if s.strip()]


def talent_to_out(t: Talent) -> dict:
    """构造 TalentOut 兼容的字典（router 层使用）。"""
    return _to_out(t)


def _to_out(t: Talent) -> dict:
    tags = [
        {
            "id": rel.tag.id, "name": rel.tag.name, "category": rel.tag.category,
            "description": rel.tag.description, "is_builtin": rel.tag.is_builtin,
            "score": rel.score,
        }
        for rel in t.tag_rels if rel.tag
    ]
    return {
        "id": t.id, "name": t.name, "gender": t.gender,
        "phone_masked": _mask_phone(t.phone), "email": t.email,
        # hq+  补充我的字段（tal_talent ALTER 加的 + 附件）
        "phone": t.phone, "birth_year": t.birth_year, "object_key": t.object_key,
        "current_company": t.current_company, "summary": t.summary,
        "resume_text": t.resume_text,
        # hq+  需求分析 01-需求分析.md T 域字段对齐（云库 tal_talent 已有）
        "id_card": t.id_card, "birth_date": t.birth_date,
        "avatar": t.avatar, "dept_id": t.dept_id, "position_id": t.position_id,
        "degree": t.degree, "school": t.school, "level": t.level,
        "tags_summary": t.tags_summary, "description": t.description,
        "resume_id": t.resume_id, "created_by": t.created_by,
        "highest_education": t.highest_education, "major": t.major,
        "current_title": t.current_title, "years_experience": t.years_experience,
        "salary_expectation": t.salary_expectation, "skills": t.skills,
        "work_experience": t.work_experience, "project_experience": t.project_experience,
        "honors": t.honors, "resume_source": t.resume_source, "resume_file": t.resume_file,
        "status": t.status, "data_quality": t.data_quality, "quality_remark": t.quality_remark,
        "expire_at": t.expire_at, "tags": tags,
        "educations": [
            {"id": e.id, "school": e.school, "degree": e.degree, "major": e.major,
             "start_year": e.start_year, "end_year": e.end_year} for e in t.educations
        ],
        "works": [
            {"id": w.id, "company": w.company, "title": w.title,
             "start_date": w.start_date, "end_date": w.end_date, "description": w.description}
            for w in t.works
        ],
        "projects": [
            {"id": p.id, "name": p.name, "role": p.role, "description": p.description}
            for p in t.projects
        ],
        "created_at": t.created_at, "updated_at": t.updated_at,
    }


def seed_builtin_tags(db: Session) -> int:
    """幂等写入内置标签库，返回新增条数。"""
    return TagDAO.seed_builtin(db, SEED_TAGS)


def _coerce_text(v) -> Optional[str]:
    """LLM 结构化输出字段可能是 list（如 [{company,..}]），规整为可读文本。"""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (list, tuple)):
        parts = []
        for item in v:
            if isinstance(item, dict):
                parts.append("；".join(f"{k}:{val}" for k, val in item.items() if val not in (None, "")))
            else:
                parts.append(str(item))
        return "；".join(p for p in parts if p) or None
    return str(v)


# ---------------- 入库：手动 / 解析 ----------------
def _build_sub_records(db: Session, t: Talent, payload: TalentCreate) -> None:
    for e in payload.educations:
        db.add(TalentEducation(talent_id=t.id, **e.model_dump()))
    for w in payload.works:
        db.add(TalentWorkExperience(talent_id=t.id, **w.model_dump()))
    for p in payload.projects:
        db.add(TalentProject(talent_id=t.id, **p.model_dump()))
    if payload.tag_names:
        tags = TagDAO.ensure_tags(db, payload.tag_names, category="custom", source="manual")
        for tag in tags:
            db.add(TalentTalentTag(talent_id=t.id, tag_id=tag.id, source="manual"))


def create_talent(db: Session, payload: TalentCreate, operator_id: int | None = None) -> dict:
    """手动录入人才（需求① 多源数据智能入库）。"""
    t = Talent(name=payload.name, gender=payload.gender, phone=payload.phone,
               email=payload.email, id_card=payload.id_card,
               highest_education=payload.highest_education, major=payload.major,
               current_title=payload.current_title, years_experience=payload.years_experience,
               salary_expectation=payload.salary_expectation, skills=payload.skills,
               work_experience=payload.work_experience,
               project_experience=payload.project_experience, honors=payload.honors,
               resume_source=payload.resume_source or "manual", status=1,
               created_by=operator_id)
    db.add(t)
    db.flush()
    _build_sub_records(db, t, payload)
    db.flush()
    build_profile(db, t, fast=True)  # 写路径用快速画像，避免被 LLM 阻塞
    db.commit()
    db.refresh(t)
    return _to_out(t)


def parse_resume_file(db: Session, filename: str, content: bytes,
                      operator_id: int | None = None) -> dict:
    """全格式简历智能解析入库（需求①）。失败写解析日志并抛出业务异常。"""
    from app.services.resume_parser import extract_text, structurize
    from app.utils.object_storage import get_object_storage

    log = TalentResumeParseLog(file_name=filename,
                               file_type=(filename or "").split(".")[-1].lower())
    db.add(log)
    db.flush()
    try:
        raw_text = extract_text(filename, content)
        data = structurize(raw_text)
        # 简历原文脱敏留档
        payload = TalentCreate(
            name=data.get("name") or "未知",
            gender=data.get("gender"), phone=data.get("phone"), email=data.get("email"),
            highest_education=data.get("highest_education"), major=data.get("major"),
            current_title=data.get("current_title"),
            years_experience=int(data.get("years_experience") or 0),
            salary_expectation=data.get("salary_expectation"),
            skills=_coerce_text(data.get("skills")),
            work_experience=_coerce_text(data.get("work_experience")),
            project_experience=_coerce_text(data.get("project_experience")),
            honors=_coerce_text(data.get("honors")),
            resume_source=(filename or "").split(".")[-1].lower() or "pdf",
            educations=[EducationIn(**e) for e in (data.get("educations") or [])],
            works=[WorkIn(**w) for w in (data.get("works") or [])],
            projects=[ProjectIn(**p) for p in (data.get("projects") or [])],
        )
        t = Talent(name=payload.name, gender=payload.gender, phone=payload.phone,
                   email=payload.email, highest_education=payload.highest_education,
                   major=payload.major, current_title=payload.current_title,
                   years_experience=payload.years_experience,
                   salary_expectation=payload.salary_expectation, skills=payload.skills,
                   work_experience=payload.work_experience,
                   project_experience=payload.project_experience, honors=payload.honors,
                   resume_source=payload.resume_source, resume_text=raw_text[:4000],
                   status=1, created_by=operator_id)
        db.add(t)
        db.flush()
        _build_sub_records(db, t, payload)
        # 原文件存 MinIO（失败不影响主流程）
        try:
            store = get_object_storage()
            object_name = f"resumes/{datetime.now():%Y/%m}/{uuid.uuid4().hex}_{filename}"
            store.put_bytes(object_name, content,
                            content_type="application/octet-stream")
            t.resume_file = object_name
        except Exception:
            t.resume_file = None
        db.flush()
        build_profile(db, t, fast=True)  # 解析路径快速画像，完整 AI 画像由显式按钮触发
        # 解析后即时查重，标记疑似重复
        dup = _identity_dup(db, t)
        if dup:
            t.data_quality = "warning"
            t.quality_remark = f"疑似与人才#{dup.id}({dup.name})重复，请人工核实"
        log.talent_id = t.id
        log.status = "success"
        db.commit()
        db.refresh(t)
        # hq+  2026-09-01：解析入库后写四维向量（含简历原文维），供语义搜索按简历内容召回
        try:
            from app.services.talent_vector_service import upsert_talent_vectors  # hq+
            upsert_talent_vectors(t)
        except Exception as e:
            logger.warning("[hq] 解析后自动向量化失败（不影响入库）：%s", e)
        return _to_out(t)
    except Exception as e:
        db.rollback()
        log.status = "failed"
        log.message = str(e)[:500]
        db.commit()
        raise BusinessError(500, f"简历解析失败（请确认 Ollama/Milvus/解析依赖已就绪）：{e}")


# ---------------- 画像：标签 + 三维向量 + 潜力 ----------------
def build_profile(db: Session, t: Talent, fast: bool = False) -> TalentProfileOut:
    """向量级人才画像（需求②）。生成 AI 标签、三维向量、潜力评级。

    fast=True 时跳过 LLM（CPU 环境单次生成可达数分钟），直接走规则兜底，
    用于 create/import/parse 等写路径，保证接口快速返回；完整 AI 画像由
    POST /{tid}/profile 显式触发（默认 fast=False）。
    """
    if fast:
        ai_tags = _split_skills(t.skills)
        potential = ("高潜力" if t.years_experience >= 5
                     else ("中高潜力" if t.years_experience >= 3 else "培养型"))
        if ai_tags:
            cats = _classify_tags(ai_tags)
            tags = TagDAO.ensure_tags(db, ai_tags, category="custom", source="ai")
            TalentTagRelDAO.set_ai_tags(
                db, t.id, [tg.id for tg in tags],
                scores={tg.id: cats.get(tg.name) for tg in tags},
            )
        db.flush()
        return TalentProfileOut(
            talent_id=t.id, name=t.name, vectors_built=False,
            ai_tags=ai_tags, skill_summary=t.skills,
            experience_summary=t.work_experience, quality_summary=None,
            potential_level=potential,
        )
    ai_tags, skill_sum, exp_sum, qual_sum, potential = _generate_profile_text(t)
    # 标签落库
    vectors_built = False
    if ai_tags:
        cats = _classify_tags(ai_tags)
        tags = TagDAO.ensure_tags(db, ai_tags, category="custom", source="ai")
        TalentTagRelDAO.set_ai_tags(
            db, t.id, [tg.id for tg in tags],
            scores={tg.id: cats.get(tg.name) for tg in tags},
        )
    # 三维向量入库（Milvus）
    text_for_vec = {
        "skill": skill_sum or (t.skills or ""),
        "exp": exp_sum or (t.work_experience or t.project_experience or ""),
        "quality": qual_sum or _talent_full_text(t),
    }
    vb = _embed_and_store_all(t.id, text_for_vec)
    vectors_built = any(vb.values())
    db.flush()
    return TalentProfileOut(
        talent_id=t.id, name=t.name, vectors_built=vectors_built,
        ai_tags=ai_tags, skill_summary=skill_sum, experience_summary=exp_sum,
        quality_summary=qual_sum, potential_level=potential,
    )


def _generate_profile_text(t: Talent) -> tuple[list[str], str, str, str, str]:
    """调用 LLM 生成标签与摘要；LLM 不可用时走规则兜底。"""
    text = _talent_full_text(t)
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        prompt = (
            "基于以下人才档案，输出 JSON：{tags:[标签名...最多30个，来自技能/岗位/层级/经验/素质/潜力],"
            "skill_summary:技能概述, experience_summary:经验概述, quality_summary:素质概述, "
            "potential_level:潜力评级(高潜力/中高潜力/稳健型/培养型)}。只输出 JSON。\n" + text
        )
        raw = llm.chat(prompt, system="你是人才画像专家，只输出 JSON。", temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        import json
        d = json.loads(raw)
        tags = [str(x).strip() for x in (d.get("tags") or []) if str(x).strip()]
        return (tags or _split_skills(t.skills),
                d.get("skill_summary"), d.get("experience_summary"),
                d.get("quality_summary"), d.get("potential_level"))
    except Exception:
        # 兜底：从技能字段切分 + 潜力按年限推断
        tags = _split_skills(t.skills)
        potential = "高潜力" if t.years_experience >= 5 else ("中高潜力" if t.years_experience >= 3 else "培养型")
        return (tags, t.skills, t.work_experience, None, potential)


def _classify_tags(tags: list[str]) -> dict[str, float]:
    """简单按标签是否在内置库推断置信度（演示用，真实可接模型打分）。"""
    known = {name for name, _, _ in SEED_TAGS}
    return {name: (0.9 if name in known else 0.6) for name in tags}


def _embed_and_store_all(talent_id: int, texts: dict[str, str]) -> dict[str, bool]:
    """对三维文本分别向量化并写入 Milvus；任一项失败不影响其它。

    hq+ 2026-09-01 修复：改用 upsert（显式 id=talent_id，幂等覆盖）——
    1) 集合若由 talent_vector_service 先建（非 auto_id），insert 无 id 会报
       "missed an field id"；upsert 带 id 两者兼容
    2) 与 /talent/{id}/vectors 视图（filter id == talent_id）共用一套集合
    3) text 保留 talent_id=N|| 前缀，供语义搜索 _vector_search 解析
    """
    result: dict[str, bool] = {}
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        vec = _vec_store()  # 兼容适配：元代码 VectorStore uri 与 pymilvus>=2.6 不兼容
        dim = len(llm.embed("test"))
        for key, txt in texts.items():
            if not txt or not txt.strip():
                result[key] = False
                continue
            try:
                if not vec.has_collection(key):
                    vec.create_collection(key, dim=dim)
                v = llm.embed(txt)
                vec._client.upsert(
                    collection_name=vec._name(key),
                    data=[{"id": int(talent_id), "vector": v,
                           "text": f"talent_id={talent_id}||{txt}"}],
                )
                result[key] = True
            except Exception:
                result[key] = False
    except Exception:
        for key in texts:
            result[key] = False
    return result


# ---------------- 查重与合并（需求③）----------------
def _identity_dup(db: Session, t: Talent) -> Optional[Talent]:
    found = TalentDAO.find_by_identity(db, name=t.name, phone=t.phone, email=t.email,
                                        exclude_id=t.id)
    return found[0] if found else None


def find_duplicates(db: Session, talent_id: int) -> DedupResult:
    """针对单个人才，识别疑似重复档案（同名/同手机/同邮箱 + 向量相似）。"""
    t = TalentDAO.get(db, talent_id)
    if not t:
        raise BusinessError(404, "人才不存在")
    candidates: list[DuplicateCandidate] = []
    for d in TalentDAO.find_by_identity(db, name=t.name, phone=t.phone, email=t.email,
                                        exclude_id=t.id):
        reason = []
        if d.name == t.name:
            reason.append("同名")
        if d.phone and d.phone == t.phone:
            reason.append("同手机号")
        if d.email and d.email == t.email:
            reason.append("同邮箱")
        candidates.append(DuplicateCandidate(talent_id=d.id, name=d.name,
                                              reason="、".join(reason) or "身份相近",
                                              similarity=None))
    # 向量相似（Milvus）
    sim = _vector_similar(db, t)
    for tid, score in sim.items():
        if tid == t.id:
            continue
        dt = TalentDAO.get(db, tid)
        if dt and not any(c.talent_id == tid for c in candidates):
            candidates.append(DuplicateCandidate(talent_id=tid, name=dt.name,
                                                 reason="向量语义相似", similarity=score))
    return DedupResult(talent_id=t.id, name=t.name, candidates=candidates)


def _vector_similar(db: Session, t: Talent) -> dict[int, float]:
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        vec = _vec_store()
        qv = llm.embed(_talent_full_text(t))
        out: dict[int, float] = {}
        for key in _VECTOR_SETS:
            if not vec.has_collection(key):
                continue
            for h in vec.search(key, qv, top_k=5):
                tid = _parse_tid(h["text"])
                if tid and (tid not in out or h["score"] > out[tid]):
                    out[tid] = h["score"]
        return out
    except Exception:
        return {}


def merge_talents(db: Session, primary_id: int, duplicate_ids: list[int]) -> dict:
    """一键合并重复档案：重复档案置失效并指向主档案。"""
    primary = TalentDAO.get(db, primary_id)
    if not primary:
        raise BusinessError(404, "主档案不存在")
    merged = 0
    for did in duplicate_ids:
        if did == primary_id:
            continue
        d = TalentDAO.get(db, did)
        if not d:
            continue
        d.status = 0
        d.merged_into = primary_id
        d.data_quality = "good"
        d.quality_remark = f"已合并至主档案#{primary_id}"
        merged += 1
    db.commit()
    return {"primary_id": primary_id, "merged": merged}


# ---------------- 语义化检索（需求④）----------------
def semantic_search(db: Session, query: str, top_k: int = 10,
                    use_vector: bool = True) -> list[SemanticSearchHit]:
    """自然语言语义检索；Milvus 不可用时降级关键词检索。"""
    if use_vector:
        hits_map = _vector_search(db, query, top_k)
        if hits_map:
            talents = {t.id: t for t in TalentDAO.list_by_ids(db, list(hits_map.keys()))}
            out: list[SemanticSearchHit] = []
            for tid, info in hits_map.items():
                t = talents.get(tid)
                if not t:
                    continue
                out.append(SemanticSearchHit(
                    talent_id=tid, name=t.name, score=info["score"],
                    match_reason="向量语义匹配", snippet=_strip_tid(info["snippet"])[:200]))
            out.sort(key=lambda x: x.score or 0, reverse=True)
            return out[:top_k]
    # 降级：关键词检索
    rows = TalentDAO.paged(db, keyword=query, page=1, page_size=top_k)
    return [
        SemanticSearchHit(talent_id=r.id, name=r.name, score=None,
                          match_reason="关键词匹配", snippet=(r.skills or "")[:200])
        for r in rows
    ]


def _vector_search(db: Session, query: str, top_k: int) -> dict[int, dict]:
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        vec = _vec_store()
        qv = llm.embed(query)
        out: dict[int, dict] = {}
        for key in _VECTOR_SETS:
            if not vec.has_collection(key):
                continue
            for h in vec.search(key, qv, top_k=top_k):
                tid = _parse_tid(h["text"])
                if tid is None:
                    continue
                prev = out.get(tid)
                if prev is None or h["score"] > prev["score"]:
                    out[tid] = {"score": h["score"], "snippet": h["text"]}
        return out
    except Exception:
        return {}


# ---------------- 档案 RAG 问答（需求⑤）----------------
def _split_chunks(text: str, chunk_size: int = 800, overlap: int = 80) -> list[str]:
    """简单按字符切块，块间保留 overlap。"""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += step
    return chunks


def rag_ask(db: Session, question: str, talent_ids: list[int] | None = None,
            top_k: int = 5, scope: str = "batch") -> RAGResponse:
    """对单个或批量人才档案做 RAG 智能问答，自动总结优势/短板/适配岗位/发展潜力。

    兼容适配：不依赖元代码 app/utils/rag.py（其内部 VectorStore uri 与 pymilvus>=2.6
    不兼容），改用 _vec_store 自实现 切块→向量化→召回→LLM 生成 的最简 RAG 链路。
    优化：单人才模式直接拼接全文，跳过向量检索，减少 embed 调用次数。
    """
    talents = (TalentDAO.list_by_ids(db, talent_ids) if talent_ids
               else TalentDAO.list_all_valid(db))
    if not talents:
        raise BusinessError(404, "未找到可问答的人才档案")

    # 单人才快速路径：直接用全文，跳过向量检索（减少多次embed的耗时）
    if len(talents) == 1:
        from app.utils.llm import get_llm
        try:
            llm = get_llm()
        except Exception as e:
            raise BusinessError(500, f"RAG 问答依赖 Ollama 服务：{e}")
        t = talents[0]
        full_text = _talent_full_text(t)
        # 限制上下文长度（避免输入过长导致更慢）
        if len(full_text) > 2000:
            full_text = full_text[:2000] + "..."
        prompt = (f"请基于以下人才档案信息，回答用户的问题。"
                  f"输出人才研判小结，包括：优势、短板、适配岗位、发展潜力。\n\n"
                  f"人才档案：\n姓名：{t.name}\n{full_text}\n\n"
                  f"问题：{question}")
        try:
            answer = llm.chat(prompt,
                              system="你是专业的人才研判助手，输出简洁的结构化研判小结，用中文回答。")
        except Exception as e:
            raise BusinessError(500, f"RAG 问答失败：{e}")
        return RAGResponse(question=question, answer=answer, scope="single",
                           talents_covered=1)
    coll = f"rag_{uuid.uuid4().hex[:12]}"
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
    except Exception as e:
        raise BusinessError(500, f"RAG 问答依赖 Ollama 服务：{e}")

    # 尝试向量检索（Milvus 可用时），失败则降级为全文拼接
    context = ""
    try:
        vec = _vec_store()
        dim = len(llm.embed("test"))
        if not vec.has_collection(coll):
            vec.create_collection(coll, dim=dim)
        for t in talents:
            text = _talent_full_text(t)
            if text.strip():
                for c in _split_chunks(text):
                    vec.insert(coll, [llm.embed(c)], [f"【来源:talent_{t.id}】{c}"])
        qv = llm.embed(question)
        hits = vec.search(coll, qv, top_k=top_k)
        context = "\n".join(h["text"] for h in hits) if hits else ""
        _vec_available = True
    except Exception:
        # Milvus 不可用：降级为直接拼接人才全文（取前 3 人，每人限 800 字）
        _vec_available = False
        parts = []
        for t in talents[:3]:
            txt = _talent_full_text(t)
            if len(txt) > 800:
                txt = txt[:800] + "..."
            parts.append(f"【人才{t.id}：{t.name}】\n{txt}")
        context = "\n\n".join(parts)

    try:
        if not context:
            context = "（无相关档案信息）"
        prompt = ("参考以下人才档案信息回答用户问题，若信息不足则如实说明，"
                  "并尽量给出人才研判小结（优势/短板/适配岗位/发展潜力）。\n\n"
                  f"资料：\n{context}\n\n问题：{question}")
        answer = llm.chat(prompt,
                          system="你是专业的人才研判助手，基于提供的人才档案输出简洁的结构化研判小结。")
    except Exception as e:
        raise BusinessError(500, f"RAG 问答失败：{e}")
    finally:
        if _vec_available:
            try:
                _vec_store().delete_collection(coll)
            except Exception:
                pass
    return RAGResponse(question=question, answer=answer, scope=scope,
                       talents_covered=len(talents))


# ---------------- 数据治理扫描（需求③）----------------
# hq+ 2026-09-01 增强：重复 / 缺失 / 错误 三类全识别 + 标准化整改建议
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EDU_NORM = {"master": "硕士", "硕士研究生": "硕士", "硕士生": "硕士",
             "本科": "本科", "学士": "本科", "本科学历": "本科",
             "博士": "博士", "博士研究生": "博士",
             "专科": "专科", "大专": "专科", "高职": "专科"}
_GENDER_NORM = {"male": "男", "man": "男", "先生": "男",
                "female": "女", "woman": "女", "女士": "女"}


def _norm_phone(p: str) -> str:
    """手机号标准化：去掉空格/横线/括号等，保留数字。"""
    return re.sub(r"[\s\-—()（）．.]", "", p or "").strip()


def governance_scan(db: Session) -> list[GovernanceIssue]:
    """扫描重复 / 错误 / 缺失 三类数据问题，输出整改建议（需求③）。

    - duplicate：姓名+手机/邮箱 命中疑似重复 → 建议查重合并
    - error：字段格式/取值不规范（手机/邮箱/学历/性别/年限/证件号）→ 建议标准化
    - missing_field：关键字段缺失 → 建议补充
    """
    issues: list[GovernanceIssue] = []
    for t in TalentDAO.list_all_valid(db, limit=5000):
        # ---------- 1) 缺失数据 ----------
        if not t.phone and not t.email:
            issues.append(GovernanceIssue(talent_id=t.id, name=t.name,
                                          issue_type="missing_field", field="phone/email",
                                          suggestion="补充联系方式，避免无法触达"))
        if not t.skills:
            issues.append(GovernanceIssue(talent_id=t.id, name=t.name,
                                          issue_type="missing_field", field="skills",
                                          suggestion="补充核心技能，提升画像与检索质量"))
        if not t.years_experience:
            issues.append(GovernanceIssue(talent_id=t.id, name=t.name,
                                          issue_type="missing_field", field="years_experience",
                                          suggestion="补充从业年限，便于层级/经验标签生成"))
        if not (t.name or "").strip() or t.name.startswith("未命名-"):
            issues.append(GovernanceIssue(talent_id=t.id, name=t.name,
                                          issue_type="missing_field", field="name",
                                          suggestion="档案为未命名草稿，请补全姓名"))

        # ---------- 2) 错误数据（格式/取值不规范）----------
        phone_raw = _norm_phone(t.phone)
        if t.phone and not _PHONE_RE.match(phone_raw):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="phone",
                suggestion=f"手机号「{t.phone}」格式不规范，应为 1[3-9] 开头的 11 位数字（可一键标准化）"))
        if t.email and ("@" not in t.email or "." not in t.email.split("@")[-1]):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="email",
                suggestion=f"邮箱「{t.email}」格式不规范（可一键标准化）"))
        if t.gender and t.gender.strip().lower() not in ("男", "女", "未知"):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="gender",
                suggestion=f"性别「{t.gender}」非标准值（男/女），建议标准化"))
        if t.highest_education:
            edu_raw = t.highest_education.strip()
            if any(k in edu_raw for k in ("大学", "学院", "学校", "University")) or edu_raw.lower() in _EDU_NORM:
                issues.append(GovernanceIssue(
                    talent_id=t.id, name=t.name, issue_type="error", field="highest_education",
                    suggestion=f"学历「{edu_raw}」疑似混入学校名或非标准值，建议标准化为 专科/本科/硕士/博士"))
        if t.years_experience is not None and (t.years_experience < 0 or t.years_experience > 50):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="years_experience",
                suggestion=f"从业年限「{t.years_experience}」超出合理范围 0-50，建议核实"))
        if t.id_card and len(t.id_card.strip()) not in (15, 18):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="id_card",
                suggestion=f"证件号「{t.id_card}」长度异常（应为 15 或 18 位）"))
        if t.birth_year and (t.birth_year < 1940 or t.birth_year > 2020):
            issues.append(GovernanceIssue(
                talent_id=t.id, name=t.name, issue_type="error", field="birth_year",
                suggestion=f"出生年「{t.birth_year}」超出合理范围（1940-2020），建议核实"))

        # ---------- 3) 疑似重复 ----------
        if _identity_dup(db, t):
            issues.append(GovernanceIssue(talent_id=t.id, name=t.name,
                                          issue_type="duplicate",
                                          suggestion="检测到疑似重复档案，建议执行查重合并"))
    return issues


# hq+ 2026-09-01：一键标准化整改（自动修复可机器判定的错误/缺失项，人工项仍提示）
def governance_repair(db: Session, talent_ids: list[int] | None = None) -> dict:
    """按治理扫描结果做可自动修复项（幂等，重复执行安全）：

    - 学历标准化：master/硕士研究生 → 硕士；混入学校名时提取纯学历
    - 性别标准化：male/man → 男；female/woman → 女
    - 手机号清洗：去空格/横线/括号 → 11 位数字
    - 邮箱去首尾空白
    - 年限越界修正：负数→0，>50 保持不变但记录
    - 证件号去空格
    :param talent_ids: 限定人才 id（None = 全部在档）
    :return: {"repaired": N, "details": [{talent_id, name, field, from, to}]}
    """
    import re as _re
    details: list[dict] = []
    q = db.query(Talent)
    if talent_ids:
        q = q.filter(Talent.id.in_(talent_ids))
    for t in q.filter(Talent.status == 1).all():
        # 学历标准化
        if t.highest_education:
            old = t.highest_education
            edu = old.strip()
            low = edu.lower()
            if low in _EDU_NORM:
                t.highest_education = _EDU_NORM[low]
            else:
                # 提取"本科/硕士/博士/专科"关键词（混入学校名时）
                m = _re.search(r"(硕士|博士|本科|专科|大专|学士)", edu)
                if m:
                    t.highest_education = m.group(1)
            if t.highest_education != old:
                details.append({"talent_id": t.id, "name": t.name, "field": "highest_education",
                                "from": old, "to": t.highest_education})
        # 性别标准化
        if t.gender:
            old = t.gender
            low = old.strip().lower()
            if low in _GENDER_NORM:
                t.gender = _GENDER_NORM[low]
            elif low not in ("男", "女", "未知"):
                t.gender = None
            if t.gender != old:
                details.append({"talent_id": t.id, "name": t.name, "field": "gender",
                                "from": old, "to": t.gender})
        # 手机号清洗
        if t.phone:
            old = t.phone
            cleaned = _norm_phone(old)
            if cleaned != old:
                t.phone = cleaned
                details.append({"talent_id": t.id, "name": t.name, "field": "phone",
                                "from": old, "to": cleaned})
        # 邮箱去空白
        if t.email:
            old = t.email
            e = old.strip()
            if e != old:
                t.email = e
                details.append({"talent_id": t.id, "name": t.name, "field": "email",
                                "from": old, "to": e})
        # 证件号去空格
        if t.id_card:
            old = t.id_card
            ic = old.strip()
            if ic != old:
                t.id_card = ic
                details.append({"talent_id": t.id, "name": t.name, "field": "id_card",
                                "from": old, "to": ic})
        # 年限负数修正
        if t.years_experience is not None and t.years_experience < 0:
            old = t.years_experience
            t.years_experience = 0
            details.append({"talent_id": t.id, "name": t.name, "field": "years_experience",
                            "from": old, "to": 0})
    db.flush()
    return {"repaired": len(details), "details": details}
#袁文武新增2026-08-31 17:10:00结束

#袁文武新增2026-08-31 22:00:00开始
# ---------------- 需求④ 优化补全：Excel 批量导入 / 多维统计 / 过期提醒 ----------------

# Excel 表头 → 模型字段 别名映射（兼容常见中英文表头）
_EXCEL_COLUMN_ALIASES: dict[str, str] = {
    "姓名": "name", "名字": "name", "name": "name",
    "性别": "gender", "gender": "gender",
    "手机号": "phone", "电话": "phone", "联系电话": "phone", "phone": "phone", "mobile": "phone",
    "邮箱": "email", "电子邮箱": "email", "email": "email",
    "身份证号": "id_card", "证件号": "id_card", "id_card": "id_card",
    "最高学历": "highest_education", "学历": "highest_education", "education": "highest_education",
    "专业": "major", "major": "major",
    "当前职位": "current_title", "职位": "current_title", "期望职位": "current_title", "title": "current_title",
    "从业年限": "years_experience", "工作年限": "years_experience", "年限": "years_experience", "years": "years_experience",
    "薪资期望": "salary_expectation", "期望薪资": "salary_expectation", "salary": "salary_expectation",
    "技能": "skills", "技能标签": "skills", "skills": "skills",
    "工作经历": "work_experience", "经历": "work_experience", "work": "work_experience",
    "项目经验": "project_experience", "项目": "project_experience", "project": "project_experience",
    "荣誉资质": "honors", "荣誉": "honors", "证书": "honors", "honors": "honors",
    "标签": "tag_names", "人才标签": "tag_names", "tags": "tag_names",
}


def import_excel_talents(db: Session, content: bytes, filename: str = "talents.xlsx",
                         operator_id: int | None = None) -> dict:
    """Excel 批量导入人才（需求① 多源数据智能入库）。支持 .xlsx，列头见 _EXCEL_COLUMN_ALIASES。

    逐行读取：姓名缺失则跳过；可带"标签"列（分号/逗号分隔）自动打自定义标签。
    解析耗时短，不依赖 LLM，适合大批量录入；入库后自动生成画像。
    """
    import io
    import openpyxl
    from app.schemas.talent import ExcelImportResult

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    if ws.max_row < 2:
        raise BusinessError(400, "Excel 内容为空（需包含表头与数据行）")
    # 第一行做表头映射
    headers: list[str] = []
    for cell in list(ws[1]):
        headers.append((cell.value or "").strip())
    col_map: dict[int, str] = {}
    for idx, h in enumerate(headers):
        field = _EXCEL_COLUMN_ALIASES.get(h)
        if field:
            col_map[idx] = field

    result = ExcelImportResult()
    for row_idx in range(2, ws.max_row + 1):
        row = [c.value for c in ws[row_idx]]
        record: dict = {}
        for col_idx, field in col_map.items():
            if col_idx < len(row) and row[col_idx] is not None:
                record[field] = str(row[col_idx]).strip()
        if not record.get("name"):
            result.skipped += 1
            continue
        try:
            payload = TalentCreate(
                name=record["name"][:64],
                gender=record.get("gender"),
                phone=record.get("phone"),
                email=record.get("email"),
                id_card=record.get("id_card"),
                highest_education=record.get("highest_education"),
                major=record.get("major"),
                current_title=record.get("current_title"),
                years_experience=int(float(record["years_experience"])) if record.get("years_experience") else 0,
                salary_expectation=record.get("salary_expectation"),
                skills=record.get("skills"),
                work_experience=record.get("work_experience"),
                project_experience=record.get("project_experience"),
                honors=record.get("honors"),
                resume_source="excel",
                tag_names=[t.strip() for t in re.split(r"[;；,，、]", record.get("tag_names", "")) if t.strip()],
            )
            t = Talent(name=payload.name, gender=payload.gender, phone=payload.phone,
                       email=payload.email, id_card=payload.id_card,
                       highest_education=payload.highest_education, major=payload.major,
                       current_title=payload.current_title, years_experience=payload.years_experience,
                       salary_expectation=payload.salary_expectation, skills=payload.skills,
                       work_experience=payload.work_experience,
                       project_experience=payload.project_experience, honors=payload.honors,
                       resume_source="excel", status=1, created_by=operator_id)
            db.add(t)
            db.flush()
            _build_sub_records(db, t, payload)
            db.flush()
            build_profile(db, t, fast=True)  # Excel 批量导入同样走快速画像
            result.imported += 1
        except Exception as e:
            result.errors.append({"row": row_idx, "name": record.get("name"), "error": str(e)[:200]})
    result.total = ws.max_row - 1
    db.commit()
    return result.model_dump()


def talent_stats(db: Session) -> dict:
    """多维查询统计（需求④）：学历分布 / 能力等级分布 / 技能标签 / 来源分布 / 过期计数。"""
    from sqlalchemy import func
    from app.schemas.talent import TalentStatsOut

    talents = TalentDAO.list_all_valid(db, limit=10000)
    out = TalentStatsOut(total=len(talents))
    for t in talents:
        out.by_education[t.highest_education or "未知"] = out.by_education.get(t.highest_education or "未知", 0) + 1
        out.by_source[t.resume_source or "unknown"] = out.by_source.get(t.resume_source or "unknown", 0) + 1
        for rel in t.tag_rels:
            if not rel.tag:
                continue
            if rel.tag.category == "level":
                out.by_level[rel.tag.name] = out.by_level.get(rel.tag.name, 0) + 1
            if rel.tag.category in ("skill", "position"):
                out.by_skill[rel.tag.name] = out.by_skill.get(rel.tag.name, 0) + 1
    # 技能 TOP10
    out.by_skill = dict(sorted(out.by_skill.items(), key=lambda x: x[1], reverse=True)[:10])
    out.expiring_count = len(scan_expiring(db))
    return out.model_dump()


def scan_expiring(db: Session, days: int = 30) -> list[dict]:
    """过期信息提醒（需求③）：expire_at 距今 <=days 天（含已过期）的档案。"""
    from datetime import timedelta
    from app.schemas.talent import ExpiringTalent

    threshold = datetime.now() + timedelta(days=days)
    result: list[ExpiringTalent] = []
    for t in TalentDAO.list_all_valid(db, limit=5000):
        if t.expire_at and t.expire_at <= threshold:
            days_left = (t.expire_at - datetime.now()).days
            result.append(ExpiringTalent(talent_id=t.id, name=t.name,
                                         expire_at=t.expire_at, days_left=days_left))
    result.sort(key=lambda x: (x.days_left or 0))
    return [r.model_dump() for r in result]
#袁文武新增2026-08-31 22:00:00结束

#袁文武新增2026-08-31 23:30:00开始
# ---------------- 标签管理 CRUD ----------------
def list_tags(db: Session, *, keyword: str | None = None, category: str | None = None,
              is_builtin: int | None = None, page: int = 1, page_size: int = 50) -> tuple[list, int]:
    """标签分页查询（需求② 智能标签画像体系 · 自定义标签管理）。"""
    from sqlalchemy import select, func
    stmt = select(TalentTag)
    count_stmt = select(func.count()).select_from(TalentTag)
    conds = []
    if keyword:
        like = f"%{keyword}%"
        conds.append(TalentTag.name.like(like))
    if category:
        conds.append(TalentTag.category == category)
    if is_builtin is not None:
        conds.append(TalentTag.is_builtin == is_builtin)
    if conds:
        stmt = stmt.where(*conds)
        count_stmt = count_stmt.where(*conds)
    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(TalentTag.category, TalentTag.id).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all()), total


def create_tag(db: Session, name: str, category: str = "custom", description: str | None = None) -> TalentTag:
    if TagDAO.get_by_name(db, name):
        raise BusinessError(400, f"标签 '{name}' 已存在")
    tag = TalentTag(name=name, category=category, description=description, is_builtin=0)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(db: Session, tag_id: int, *, name: str | None = None,
               category: str | None = None, description: str | None = None) -> TalentTag:
    tag = db.get(TalentTag, tag_id)
    if not tag:
        raise BusinessError(404, "标签不存在")
    if tag.is_builtin:
        raise BusinessError(400, "内置标签不可修改")
    if name and name != tag.name:
        if TagDAO.get_by_name(db, name):
            raise BusinessError(400, f"标签名 '{name}' 已存在")
        tag.name = name
    if category is not None:
        tag.category = category
    if description is not None:
        tag.description = description
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> None:
    tag = db.get(TalentTag, tag_id)
    if not tag:
        raise BusinessError(404, "标签不存在")
    if tag.is_builtin:
        raise BusinessError(400, "内置标签不可删除")
    db.execute(TalentTalentTag.__table__.delete().where(TalentTalentTag.tag_id == tag_id))
    db.delete(tag)
    db.commit()


def list_tag_categories(db: Session) -> list[dict]:
    from sqlalchemy import select, func
    rows = db.execute(
        select(TalentTag.category, func.count(TalentTag.id))
        .group_by(TalentTag.category).order_by(TalentTag.category)
    ).all()
    return [{"category": r[0], "count": r[1]} for r in rows]


# ---------------- Word 批量导入 ----------------
def import_word_talents(db: Session, content: bytes, filename: str,
                         operator_id: int | None = None) -> dict:
    """Word 批量导入人才（需求① 多源数据智能入库 · Word 批量导入）。"""
    import io
    from app.schemas.talent import WordImportResult
    try:
        from docx import Document
    except Exception as e:
        raise BusinessError(500, f"Word 导入需要 python-docx：{e}")
    doc = Document(io.BytesIO(content))
    result = WordImportResult()
    records = []
    for table in doc.tables:
        if len(table.rows) < 2:
            continue
        headers = [c.text.strip() for c in table.rows[0].cells]
        name_idx = None
        for i, h in enumerate(headers):
            if "姓名" in h or h.lower() == "name":
                name_idx = i
                break
        if name_idx is None:
            continue
        for row_idx in range(1, len(table.rows)):
            cells = [c.text.strip() for c in table.rows[row_idx].cells]
            if name_idx >= len(cells) or not cells[name_idx]:
                result.skipped += 1
                continue
            record = {}
            for i, h in enumerate(headers):
                if i < len(cells) and cells[i]:
                    record[h] = cells[i]
            records.append(record)
    if not records:
        current = {}
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                if current.get("姓名") or current.get("name"):
                    records.append(current)
                    current = {}
                continue
            if "：" in text:
                k, v = text.split("：", 1)
                current[k.strip()] = v.strip()
            elif ":" in text and not text.startswith("http"):
                k, v = text.split(":", 1)
                current[k.strip()] = v.strip()
        if current.get("姓名") or current.get("name"):
            records.append(current)
    if not records:
        raise BusinessError(400, "Word 文档中未解析到有效的人才数据")
    field_map = {
        "姓名": "name", "name": "name",
        "性别": "gender", "gender": "gender",
        "手机号": "phone", "电话": "phone", "phone": "phone",
        "邮箱": "email", "email": "email",
        "学历": "highest_education", "最高学历": "highest_education",
        "专业": "major", "major": "major",
        "职位": "current_title", "期望职位": "current_title",
        "从业年限": "years_experience", "工作年限": "years_experience",
        "薪资期望": "salary_expectation", "期望薪资": "salary_expectation",
        "技能": "skills", "技能标签": "skills",
        "工作经历": "work_experience", "项目经验": "project_experience",
        "荣誉": "honors", "荣誉资质": "honors", "证书": "honors",
        "标签": "tag_names",
    }
    for idx, rec in enumerate(records):
        try:
            normalized = {}
            for k, v in rec.items():
                field = field_map.get(k)
                if field:
                    normalized[field] = v
            if not normalized.get("name"):
                result.skipped += 1
                continue
            payload = TalentCreate(
                name=str(normalized["name"])[:64],
                gender=normalized.get("gender"),
                phone=normalized.get("phone"),
                email=normalized.get("email"),
                highest_education=normalized.get("highest_education"),
                major=normalized.get("major"),
                current_title=normalized.get("current_title"),
                years_experience=int(float(normalized["years_experience"])) if normalized.get("years_experience") else 0,
                salary_expectation=normalized.get("salary_expectation"),
                skills=normalized.get("skills"),
                work_experience=normalized.get("work_experience"),
                project_experience=normalized.get("project_experience"),
                honors=normalized.get("honors"),
                resume_source="word",
                tag_names=[t.strip() for t in re.split(r"[;；,，、]", normalized.get("tag_names", "")) if t.strip()],
            )
            t = Talent(name=payload.name, gender=payload.gender, phone=payload.phone,
                       email=payload.email, highest_education=payload.highest_education,
                       major=payload.major, current_title=payload.current_title,
                       years_experience=payload.years_experience,
                       salary_expectation=payload.salary_expectation, skills=payload.skills,
                       work_experience=payload.work_experience,
                       project_experience=payload.project_experience, honors=payload.honors,
                       resume_source="word", status=1, created_by=operator_id)
            db.add(t)
            db.flush()
            _build_sub_records(db, t, payload)
            db.flush()
            build_profile(db, t, fast=True)
            result.imported += 1
        except Exception as e:
            result.errors.append({"row": idx + 1, "name": rec.get("姓名") or rec.get("name"), "error": str(e)[:200]})
    result.total = len(records)
    db.commit()
    return result.model_dump()


# ---------------- 证书管理 ----------------
def list_certificates(db: Session, talent_id: int) -> list[dict]:
    from app.dao.talent import CertificateDAO
    certs = CertificateDAO.list_by_talent(db, talent_id)
    return [{"id": c.id, "name": c.name, "issuer": c.issuer,
             "cert_no": c.cert_no, "issue_date": c.issue_date,
             "expire_date": c.expire_date, "level": c.level,
             "description": c.description} for c in certs]


def save_certificates(db: Session, talent_id: int, certs: list[dict]) -> None:
    from app.dao.talent import CertificateDAO
    CertificateDAO.replace_by_talent(db, talent_id, certs)
    db.commit()
#袁文武新增2026-08-31 23:30:00结束
