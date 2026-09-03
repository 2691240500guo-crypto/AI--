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
from app.dao.talent_report import TalentReportDAO  # 袁文武 2026-09-02：AI 报告三大字段
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


# ---------------- 内置 100+ 多维度标签库（8 大维度）----------------
# 袁文武 2026-09-03 优化：扩展到 100+ 标签，覆盖 8 大维度
# 维度：skill(专业技能) / level(能力层级) / exp(从业经验) / quality(综合素质)
#       position(适配岗位) / potential(潜力评级) / specialty(职业特长) / industry(行业经验)
SEED_TAGS: list[tuple[str, str, str]] = [
    # === 专业技能 skill（40+） ===
    ("Python", "skill", "编程语言"), ("Java", "skill", "编程语言"), ("Go", "skill", "编程语言"),
    ("C++", "skill", "编程语言"), ("JavaScript", "skill", "编程语言"), ("TypeScript", "skill", "编程语言"),
    ("Rust", "skill", "编程语言"), ("PHP", "skill", "编程语言"), ("C#", "skill", "编程语言"),
    ("SQL", "skill", "数据库"), ("MySQL", "skill", "关系数据库"), ("PostgreSQL", "skill", "关系数据库"),
    ("Oracle", "skill", "关系数据库"), ("Redis", "skill", "缓存"), ("MongoDB", "skill", "文档数据库"),
    ("Elasticsearch", "skill", "搜索引擎"), ("Kafka", "skill", "消息队列"),
    ("Linux", "skill", "操作系统"), ("Docker", "skill", "容器化"), ("Kubernetes", "skill", "编排"),
    ("FastAPI", "skill", "Web框架"), ("Django", "skill", "Web框架"), ("Flask", "skill", "Web框架"),
    ("Spring Boot", "skill", "Java框架"), ("Spring Cloud", "skill", "微服务"),
    ("Vue", "skill", "前端框架"), ("React", "skill", "前端框架"), ("Angular", "skill", "前端框架"),
    ("PyTorch", "skill", "深度学习"), ("TensorFlow", "skill", "深度学习"),
    ("NLP", "skill", "自然语言处理"), ("计算机视觉", "skill", "CV"),
    ("机器学习", "skill", "AI"), ("深度学习", "skill", "AI"), ("AIGC", "skill", "AI"),
    ("RAG", "skill", "AI"), ("LangChain", "skill", "AI框架"), ("Agent", "skill", "AI"),
    ("数据分析", "skill", "数据"), ("数据建模", "skill", "数据"), ("数据治理", "skill", "数据"),
    ("ETL", "skill", "数据集成"), ("大数据", "skill", "数据"), ("Hadoop", "skill", "大数据"),
    ("Spark", "skill", "大数据"), ("Flink", "skill", "大数据"),
    ("Tableau", "skill", "可视化"), ("PowerBI", "skill", "可视化"), ("Excel", "skill", "办公"),
    ("UI设计", "skill", "设计"), ("UX设计", "skill", "设计"), ("产品设计", "skill", "产品"),
    ("需求分析", "skill", "产品"), ("原型设计", "skill", "产品"),
    ("项目管理", "skill", "通用"), ("敏捷开发", "skill", "研发管理"), ("DevOps", "skill", "工程效能"),
    ("CI/CD", "skill", "工程效能"), ("自动化测试", "skill", "测试"), ("性能测试", "skill", "测试"),
    ("信息安全", "skill", "安全"), ("网络安全", "skill", "安全"), ("渗透测试", "skill", "安全"),
    ("人力资源管理", "skill", "HR"), ("招聘", "skill", "HR"), ("薪酬绩效", "skill", "HR"),
    ("培训发展", "skill", "HR"), ("人才发展", "skill", "HR"),
    ("财务管理", "skill", "财务"), ("市场营销", "skill", "市场"), ("销售管理", "skill", "销售"),
    ("运营管理", "skill", "运营"), ("内容运营", "skill", "运营"), ("用户运营", "skill", "运营"),
    # === 能力层级 level（10） ===
    ("初级", "level", "0-2年"), ("中级", "level", "2-5年"), ("高级", "level", "5-8年"),
    ("资深", "level", "8年以上"), ("骨干", "level", "团队中坚"),
    ("专家", "level", "领域权威"), ("架构师", "level", "技术决策"),
    ("管理者", "level", "带团队"), ("负责人", "level", "独立负责"), ("技术总监", "level", "高管"),
    # === 从业经验 exp（12） ===
    ("3年以上经验", "exp", "年限"), ("5年以上经验", "exp", "年限"),
    ("8年以上经验", "exp", "年限"), ("10年以上经验", "exp", "年限"),
    ("大型项目经验", "exp", "项目规模"), ("从0到1经验", "exp", "建设经验"),
    ("跨部门协作", "exp", "协作"), ("带团队经验", "exp", "管理经验"),
    ("创业经历", "exp", "特殊经历"), ("海外经历", "exp", "特殊经历"),
    ("甲方经验", "exp", "经历类型"), ("乙方经验", "exp", "经历类型"),
    # === 综合素质 quality（15） ===
    ("沟通能力强", "quality", "软技能"), ("抗压能力强", "quality", "软技能"),
    ("学习能力强", "quality", "软技能"), ("责任心强", "quality", "软技能"),
    ("团队协作", "quality", "软技能"), ("创新意识", "quality", "软技能"),
    ("逻辑思维强", "quality", "软技能"), ("领导力", "quality", "软技能"),
    ("执行力强", "quality", "软技能"), ("客户导向", "quality", "软技能"),
    ("结果导向", "quality", "软技能"), ("结构化思维", "quality", "思维"),
    ("系统思维", "quality", "思维"), ("数据驱动", "quality", "思维"),
    ("自驱力强", "quality", "特质"),
    # === 适配岗位 position（15） ===
    ("后端工程师", "position", "研发"), ("前端工程师", "position", "研发"),
    ("全栈工程师", "position", "研发"), ("算法工程师", "position", "AI"),
    ("数据工程师", "position", "数据"), ("数据分析师", "position", "数据"),
    ("产品经理", "position", "产品"), ("项目经理", "position", "管理"),
    ("测试工程师", "position", "质量"), ("运维工程师", "position", "运维"),
    ("架构师", "position", "技术"), ("技术总监", "position", "管理"),
    ("UI设计师", "position", "设计"), ("HRBP", "position", "HR"),
    ("运营经理", "position", "运营"),
    # === 潜力评级 potential（5） ===
    ("高潜力", "potential", "P9"), ("中高潜力", "potential", "P8"),
    ("稳健型", "potential", "P7"), ("培养型", "potential", "P6"), ("待观察", "potential", "P5"),
    # === 职业特长 specialty（10）===
    ("技术攻坚", "specialty", "特长"), ("架构设计", "specialty", "特长"),
    ("团队管理", "specialty", "特长"), ("业务理解", "specialty", "特长"),
    ("数据分析", "specialty", "特长"), ("产品规划", "specialty", "特长"),
    ("技术创新", "specialty", "特长"), ("成本优化", "specialty", "特长"),
    ("流程优化", "specialty", "特长"), ("跨部门协调", "specialty", "特长"),
    # === 行业经验 industry（12）===
    ("互联网行业", "industry", "行业"), ("金融行业", "industry", "行业"),
    ("制造业", "industry", "行业"), ("电商行业", "industry", "行业"),
    ("教育行业", "industry", "行业"), ("医疗行业", "industry", "行业"),
    ("政企行业", "industry", "行业"), ("汽车行业", "industry", "行业"),
    ("能源行业", "industry", "行业"), ("零售行业", "industry", "行业"),
    ("房地产行业", "industry", "行业"), ("物流行业", "industry", "行业"),
]
# 统计：skill(67) + level(10) + exp(12) + quality(15) + position(15) + potential(5) + specialty(10) + industry(12) = 146
# 真正的百级标签体系


# 标签维度中文名称映射
TAG_DIM_LABELS = {
    "skill": "专业技能",
    "level": "能力层级",
    "exp": "从业经验",
    "quality": "综合素质",
    "position": "适配岗位",
    "potential": "潜力评级",
    "specialty": "职业特长",
    "industry": "行业经验",
}
# 标签维度配色
TAG_DIM_COLORS = {
    "skill": "success",
    "level": "warning",
    "exp": "primary",
    "quality": "info",
    "position": "danger",
    "potential": "warning",
    "specialty": "success",
    "industry": "primary",
}


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
        # 原文件存 MinIO（失败不影响主流程，但要写日志+同时维护 object_key/resume_file 兼容前端 v-if）
        try:
            store = get_object_storage()
            object_name = f"resumes/{datetime.now():%Y/%m}/{uuid.uuid4().hex}_{filename}"
            store.put_bytes(object_name, content,
                            content_type="application/octet-stream")
            t.resume_file = object_name
            t.object_key = object_name  # hq+ 2026-09-03：同时写 object_key，兼容 list.vue 附件列 v-if 三字段判断
        except Exception as e:
            # hq+ 2026-09-03：之前 try/except Exception: t.resume_file = None 会静默吞 MinIO 异常
            #   导致 status=success 但 resume_file=None（前端附件列空）。现在记 warning + 写解析日志 message，
            #   便于排查 MinIO 配置（如端口错）问题。
            logger.warning("[hq] MinIO 存简历失败(允许主流程继续): talent_id=%s err=%s", t.id, e)
            t.resume_file = None
            t.object_key = None
            log.message = f"MinIO 存简历失败: {str(e)[:300]}"
        db.flush()
        build_profile(db, t, fast=True)  # 解析路径快速画像，完整 AI 画像由显式按钮触发
        _ensure_ai_report_three_fields(db, t)  # 袁文武 2026-09-02：自动生成 AI 报告三大字段
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



# ---------------- 袁文武 2026-09-02：AI 报告三大字段规则判定 ----------------
def _calc_ability_level(t: Talent) -> str:
    """基于年限 + 学历 + 职位关键词判定能力等级（P5初级 / P6中级 / P7高级 / P8专家）。"""
    years = t.years_experience or 0
    edu = (t.highest_education or "").lower()
    title = (t.current_title or "").lower()

    # 职位关键词加权
    expert_keywords = ["专家", "架构师", "总监", "cto", "首席", "研究员"]
    senior_keywords = ["高级", "资深", "主管", "经理", "leader", "lead", "负责人", "技术主管"]
    mid_keywords = ["工程师", "开发", "专员", "顾问", "分析师"]

    if any(k in title for k in expert_keywords) or years >= 10:
        return "P8专家"
    if any(k in title for k in senior_keywords) or years >= 6:
        return "P7高级"
    if any(k in title for k in mid_keywords) or years >= 2:
        return "P6中级"
    return "P5初级"


def _calc_composite_score(t: Talent) -> int:
    """基于多维度加权计算综合评分（0-100）。
    维度：工作年限(30分) + 学历(15分) + 技能丰富度(25分) + 职位层级(20分) + 项目经验(10分)。
    """
    score = 0
    years = t.years_experience or 0
    edu = (t.highest_education or "").lower()
    title = (t.current_title or "")
    skills_text = t.skills or ""
    work_exp = t.work_experience or ""
    proj_exp = t.project_experience or ""

    # 1. 工作年限（30分）：0-15年线性，15年以上满分
    year_score = min(years / 15.0, 1.0) * 30
    score += year_score

    # 2. 学历（15分）
    edu_score_map = {
        "博士": 15, "博士后": 15, "phd": 15, "doctor": 15,
        "硕士": 12, "研究生": 12, "master": 12, "mba": 12,
        "本科": 9, "学士": 9, "bachelor": 9,
        "大专": 6, "专科": 6, "college": 6, "associate": 6,
        "高中": 3, "中专": 3,
    }
    edu_score = 0
    for k, v in edu_score_map.items():
        if k in edu:
            edu_score = v
            break
    score += edu_score

    # 3. 技能丰富度（25分）：按技能标签数量
    skill_count = len([s for s in re.split(r"[;；,，、\s]+", skills_text) if s.strip()])
    if skill_count >= 15:
        score += 25
    elif skill_count >= 10:
        score += 20
    elif skill_count >= 6:
        score += 15
    elif skill_count >= 3:
        score += 10
    elif skill_count >= 1:
        score += 5

    # 4. 职位层级（20分）
    title_lower = title.lower()
    if any(k in title_lower for k in ["专家", "架构师", "总监", "cto", "首席"]):
        score += 20
    elif any(k in title_lower for k in ["高级", "资深", "主管", "经理", "leader", "负责人"]):
        score += 15
    elif any(k in title_lower for k in ["工程师", "开发", "专员", "顾问", "分析师"]):
        score += 10
    else:
        score += 5

    # 5. 项目经验（10分）
    if proj_exp and len(proj_exp) > 500:
        score += 10
    elif proj_exp and len(proj_exp) > 200:
        score += 7
    elif work_exp and len(work_exp) > 200:
        score += 5
    else:
        score += 2

    return max(0, min(100, int(round(score))))


def _build_experience_summary(t: Talent) -> str:
    """基于工作经验 + 年限 + 职位生成从业经验总结（2-3 句话）。"""
    years = t.years_experience or 0
    title = t.current_title or "从业者"
    edu = t.highest_education or ""
    skills_text = t.skills or ""
    work_exp = t.work_experience or ""

    # 提取核心技能前 3 个
    skill_list = [s.strip() for s in re.split(r"[;；,，、\s]+", skills_text) if s.strip()]
    core_skills = "、".join(skill_list[:3]) if skill_list else ""

    parts = []
    # 第一句：基本背景
    if edu:
        parts.append(f"{edu}学历，{years}年{title}从业经验。")
    else:
        parts.append(f"{years}年{title}从业经验。")

    # 第二句：核心技能
    if core_skills:
        parts.append(f"核心技能方向：{core_skills}。")

    # 第三句：经验亮点（取工作经验前 60 字）
    if work_exp:
        clean = re.sub(r"\s+", "", work_exp)[:60]
        if clean:
            parts.append(f"主要经历：{clean}...")

    return "".join(parts) if parts else ""


def _ensure_ai_report_three_fields(db: Session, t: Talent) -> None:
    """解析后自动生成 AI 报告三大字段（能力等级 / 综合评分 / 从业经验）并写入报告表。
    若报告记录已存在则只补空字段，不存在则新建。"""
    import json
    ability = _calc_ability_level(t)
    score = _calc_composite_score(t)
    exp_summary = _build_experience_summary(t)

    # 技能列表也一并写入（从 skills 字段拆分）
    skill_list = [s.strip() for s in re.split(r"[;；,，、\s]+", t.skills or "") if s.strip()]
    # 潜力评级（沿用 build_profile 的规则）
    potential = ("高潜力" if (t.years_experience or 0) >= 5
                 else ("中高潜力" if (t.years_experience or 0) >= 3 else "培养型"))

    fields = {
        "ability_level": ability,
        "composite_score": score,
        "experience_summary": exp_summary,
        "skills": json.dumps(skill_list, ensure_ascii=False) if skill_list else None,
        "potential": potential,
        "highlights": json.dumps([], ensure_ascii=False),
        "shortcomings": json.dumps([], ensure_ascii=False),
        "fit_positions": json.dumps([], ensure_ascii=False),
    }
    try:
        TalentReportDAO.upsert(db, t.id, fields)
    except Exception as e:
        # 报告写入失败不影响主流程
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("[袁文武] 解析后写入 AI 报告三大字段失败（不影响入库）：%s", e)


# ---------------- 画像：标签 + 四维向量 + 潜力 + 多维度分组 ----------------
# 袁文武 2026-09-03 优化：8 大维度百级标签体系 + 规则智能推导 + LLM 增强
def build_profile(db: Session, t: Talent, fast: bool = False) -> TalentProfileOut:
    """向量级人才画像（需求②）。生成多维度 AI 标签、四维向量、潜力评级。

    8 大标签维度：专业技能 / 能力层级 / 从业经验 / 综合素质 / 适配岗位 /
                  潜力评级 / 职业特长 / 行业经验

    fast=True 时跳过 LLM，用规则智能推导标签，保证接口快速返回；
    完整 AI 画像由 POST /{tid}/profile 显式触发。
    """
    from datetime import datetime

    if fast:
        # 快速画像：规则推导多维度标签，不生成向量
        tags_by_dim = _derive_tags_by_rules(t)
        all_tags = _flatten_tags(tags_by_dim)
        potential = tags_by_dim.get("potential", ["培养型"])[0]
        if all_tags:
            cats = _classify_tags(all_tags)
            tags = TagDAO.ensure_tags(db, all_tags, category="custom", source="ai")
            TalentTagRelDAO.set_ai_tags(
                db, t.id, [tg.id for tg in tags],
                scores={tg.id: cats.get(tg.name, 0.6) for tg in tags},
            )
        db.flush()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return TalentProfileOut(
            talent_id=t.id, name=t.name, vectors_built=False,
            ai_tags=all_tags, skill_summary=t.skills,
            experience_summary=t.work_experience, quality_summary=None,
            potential_level=potential,
            tags_by_dim=tags_by_dim, tag_count=len(all_tags),
            generate_mode="fast", profile_updated_at=now_str,
        )

    # 完整画像：LLM 生成（失败走规则兜底）
    tags_by_dim, skill_sum, exp_sum, qual_sum, potential, mode = _generate_profile_full(t)
    all_tags = _flatten_tags(tags_by_dim)

    # 标签落库
    vectors_built = False
    if all_tags:
        cats = _classify_tags(all_tags)
        tags = TagDAO.ensure_tags(db, all_tags, category="custom", source="ai")
        TalentTagRelDAO.set_ai_tags(
            db, t.id, [tg.id for tg in tags],
            scores={tg.id: cats.get(tg.name, 0.6) for tg in tags},
        )

    # 四维向量入库（Milvus）：统一走 talent_vector_service.upsert_talent_vectors
    # （2026-09-03：收敛第二个写实现 _embed_and_store_all，保证 resume 文本带 meta 头、
    #   所有写入口同一契约，匹配/语义搜索读取一致）
    from app.services.talent_vector_service import upsert_talent_vectors
    vb = upsert_talent_vectors(t)
    vectors_built = any(vb.values())

    db.flush()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return TalentProfileOut(
        talent_id=t.id, name=t.name, vectors_built=vectors_built,
        ai_tags=all_tags, skill_summary=skill_sum, experience_summary=exp_sum,
        quality_summary=qual_sum, potential_level=potential,
        tags_by_dim=tags_by_dim, tag_count=len(all_tags),
        generate_mode=mode, profile_updated_at=now_str,
    )


def _flatten_tags(tags_by_dim: dict[str, list[str]]) -> list[str]:
    """把分组标签拍平成去重的一维列表。"""
    seen = set()
    out = []
    for dim, tags in tags_by_dim.items():
        for tag in tags:
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def _generate_profile_full(t: Talent) -> tuple[dict[str, list[str]], str, str, str, str, str]:
    """生成完整画像（LLM 优先，规则兜底）。

    返回：(tags_by_dim, skill_sum, exp_sum, qual_sum, potential, mode)
    """
    text = _talent_full_text(t)
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        prompt = (
            "你是资深人才画像专家。请基于以下人才档案，生成结构化的人才画像。\n"
            "严格按 JSON 格式输出，不要输出其他文字。\n"
            "JSON 结构如下（所有字段必填，tags_* 字段为字符串数组）：\n"
            "{\n"
            '  "tags_skill": ["Python","Java",...],      // 专业技能标签，10-20个\n'
            '  "tags_level": ["高级","骨干",...],         // 能力层级标签，1-2个\n'
            '  "tags_exp": ["5年以上经验","大型项目经验",...], // 从业经验标签，3-5个\n'
            '  "tags_quality": ["沟通能力强","学习能力强",...], // 综合素质标签，5-8个\n'
            '  "tags_position": ["后端工程师",...],       // 适配岗位标签，2-3个\n'
            '  "tags_potential": ["中高潜力"],             // 潜力评级，1个（高潜力/中高潜力/稳健型/培养型）\n'
            '  "tags_specialty": ["技术攻坚","架构设计",...], // 职业特长标签，3-5个\n'
            '  "tags_industry": ["互联网行业",...],        // 行业经验标签，1-3个\n'
            '  "skill_summary": "技能概述（100字内）",\n'
            '  "experience_summary": "经验概述（100字内）",\n'
            '  "quality_summary": "素质概述（80字内）",\n'
            '  "potential_level": "潜力评级"\n'
            "}\n"
            "注意：\n"
            "1. 标签必须来自真实的人才档案，不要凭空捏造\n"
            "2. 技能标签尽量具体（技术栈、工具、方法论）\n"
            "3. 层级/潜力标签必须有依据（年限、职位、经验深度）\n"
            "4. 特长标签要突出差异化优势\n\n"
            "人才档案：\n" + text
        )
        raw = llm.chat(prompt, system="你是专业的人才画像专家，只输出合法 JSON。", temperature=0.2)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        import json
        d = json.loads(raw)

        tags_by_dim = {
            "skill": _clean_tags(d.get("tags_skill", [])),
            "level": _clean_tags(d.get("tags_level", [])),
            "exp": _clean_tags(d.get("tags_exp", [])),
            "quality": _clean_tags(d.get("tags_quality", [])),
            "position": _clean_tags(d.get("tags_position", [])),
            "potential": _clean_tags(d.get("tags_potential", [])),
            "specialty": _clean_tags(d.get("tags_specialty", [])),
            "industry": _clean_tags(d.get("tags_industry", [])),
        }
        potential = d.get("potential_level") or (tags_by_dim["potential"][0] if tags_by_dim["potential"] else None)

        # 校验：至少要有技能标签
        if not tags_by_dim["skill"]:
            raise ValueError("LLM 未生成技能标签")

        return (tags_by_dim,
                d.get("skill_summary", ""), d.get("experience_summary", ""),
                d.get("quality_summary", ""), potential, "llm")
    except Exception:
        # 兜底：规则推导
        tags_by_dim = _derive_tags_by_rules(t)
        potential = tags_by_dim.get("potential", ["培养型"])[0]
        return (tags_by_dim, t.skills, t.work_experience, None, potential, "rule")


def _clean_tags(tags: list) -> list[str]:
    """清洗标签列表，去空去重。"""
    seen = set()
    out = []
    for t in tags or []:
        s = str(t).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _derive_tags_by_rules(t: Talent) -> dict[str, list[str]]:
    """用规则从人才档案中推导 8 维度标签（零 AI 依赖，fast 模式和兜底都用）。

    策略：
    1. 技能标签：从 skills 字段切分 + 匹配内置标签库
    2. 能力层级：根据年限 + 职位关键词推断
    3. 从业经验：根据年限 + 工作经历关键词推断
    4. 综合素质：根据职位/层级推断典型软技能
    5. 适配岗位：根据技能 + 职位关键词匹配
    6. 潜力评级：根据年限 + 职位推断
    7. 职业特长：根据技能深度推断
    8. 行业经验：从工作经历/公司中提取行业关键词
    """
    result = {
        "skill": [], "level": [], "exp": [], "quality": [],
        "position": [], "potential": [], "specialty": [], "industry": [],
    }

    years = t.years_experience or 0
    title = (t.current_title or "").lower()
    skills_text = t.skills or ""
    work_text = t.work_experience or ""
    project_text = t.project_experience or ""
    company = (t.current_company or "").lower()
    full_text = f"{skills_text} {work_text} {project_text} {title}".lower()

    # --- 1. 专业技能 ---
    skill_tags = []
    # 从内置标签库匹配
    for name, cat, sub in SEED_TAGS:
        if cat != "skill":
            continue
        if name.lower() in full_text:
            skill_tags.append(name)
    # 从 skills 字段切分补充
    split_skills = _split_skills(skills_text)
    for s in split_skills:
        if s and s not in skill_tags and len(s) >= 2:
            skill_tags.append(s)
    result["skill"] = skill_tags[:20]  # 最多 20 个

    # --- 2. 能力层级 ---
    level_tags = []
    if "总监" in title or "cto" in title:
        level_tags.append("技术总监")
    elif "架构师" in title or "架构" in title:
        level_tags.append("架构师")
    elif "专家" in title:
        level_tags.append("专家")
    elif "负责人" in title:
        level_tags.append("负责人")
    elif "经理" in title or "主管" in title:
        level_tags.append("管理者")
    elif years >= 8:
        level_tags.append("资深")
    elif years >= 5:
        level_tags.append("高级")
    elif years >= 2:
        level_tags.append("中级")
    else:
        level_tags.append("初级")
    # 骨干：5年以上 + 非管理岗
    if years >= 5 and "经理" not in title and "总监" not in title and "架构师" not in title:
        level_tags.append("骨干")
    result["level"] = level_tags[:2]

    # --- 3. 从业经验 ---
    exp_tags = []
    if years >= 10:
        exp_tags.append("10年以上经验")
    elif years >= 8:
        exp_tags.append("8年以上经验")
    elif years >= 5:
        exp_tags.append("5年以上经验")
    elif years >= 3:
        exp_tags.append("3年以上经验")

    if any(kw in full_text for kw in ["大型项目", "亿级", "百万级", "千万级", "高并发", "大规模"]):
        exp_tags.append("大型项目经验")
    if any(kw in full_text for kw in ["从0到1", "从零到一", "搭建", "搭建了", "创建", "组建"]):
        exp_tags.append("从0到1经验")
    if "跨部门" in full_text or "跨团队" in full_text:
        exp_tags.append("跨部门协作")
    if any(kw in title for kw in ["经理", "主管", "负责人", "总监", "lead"]):
        exp_tags.append("带团队经验")
    if any(kw in full_text for kw in ["创业", "初创"]):
        exp_tags.append("创业经历")
    result["exp"] = exp_tags[:5]

    # --- 4. 综合素质 ---
    quality_tags = []
    if years >= 5:
        quality_tags.extend(["责任心强", "执行力强", "结果导向"])
    if "管理" in title or "经理" in title or "负责人" in title:
        quality_tags.extend(["团队协作", "沟通能力强", "领导力"])
    if years >= 8:
        quality_tags.extend(["抗压能力强", "结构化思维"])
    if "数据" in full_text or "分析" in full_text:
        quality_tags.append("数据驱动")
    if any(kw in full_text for kw in ["学习", "新技术", "研究"]):
        quality_tags.append("学习能力强")
    if not quality_tags:
        quality_tags = ["责任心强", "团队协作", "执行力强"]
    # 去重
    seen = set()
    quality_tags = [x for x in quality_tags if not (x in seen or seen.add(x))]
    result["quality"] = quality_tags[:8]

    # --- 5. 适配岗位 ---
    pos_tags = []
    # 从内置岗位标签匹配
    for name, cat, sub in SEED_TAGS:
        if cat != "position":
            continue
        if name.lower() in full_text or name.lower() in title:
            pos_tags.append(name)
    # 基于技能推断
    if not pos_tags:
        if any(k in full_text for k in ["python", "java", "go", "后端", "spring", "django", "fastapi"]):
            pos_tags.append("后端工程师")
        if any(k in full_text for k in ["vue", "react", "前端", "javascript", "css"]):
            pos_tags.append("前端工程师")
        if any(k in full_text for k in ["算法", "机器学习", "深度学习", "nlp", "pytorch"]):
            pos_tags.append("算法工程师")
        if any(k in full_text for k in ["产品", "需求", "原型"]):
            pos_tags.append("产品经理")
        if any(k in full_text for k in ["测试", "自动化测试", "qa"]):
            pos_tags.append("测试工程师")
        if any(k in full_text for k in ["运维", "devops", "k8s", "docker"]):
            pos_tags.append("运维工程师")
        if any(k in full_text for k in ["数据", "sql", "etl", "数仓"]):
            pos_tags.append("数据工程师")
    result["position"] = pos_tags[:3]

    # --- 6. 潜力评级 ---
    if years >= 8 and level_tags and any(l in level_tags for l in ["资深", "专家", "架构师", "技术总监"]):
        potential = "高潜力"
    elif years >= 5:
        potential = "中高潜力"
    elif years >= 3:
        potential = "稳健型"
    else:
        potential = "培养型"
    result["potential"] = [potential]

    # --- 7. 职业特长 ---
    specialty_tags = []
    if any(k in full_text for k in ["架构", "系统设计", "技术方案"]):
        specialty_tags.append("架构设计")
    if any(k in full_text for k in ["攻坚", "难题", "疑难", "性能优化"]):
        specialty_tags.append("技术攻坚")
    if "管理" in title or "经理" in title or "负责人" in title:
        specialty_tags.append("团队管理")
    if any(k in full_text for k in ["业务", "产品", "需求", "行业"]):
        specialty_tags.append("业务理解")
    if any(k in full_text for k in ["数据", "分析", "统计"]):
        specialty_tags.append("数据分析")
    if any(k in full_text for k in ["产品规划", "产品设计", "roadmap"]):
        specialty_tags.append("产品规划")
    if any(k in full_text for k in ["创新", "专利", "研究", "研发"]):
        specialty_tags.append("技术创新")
    if any(k in full_text for k in ["成本", "优化", "效率"]):
        specialty_tags.append("成本优化")
    if any(k in full_text for k in ["流程", "规范", "标准化"]):
        specialty_tags.append("流程优化")
    if any(k in full_text for k in ["协调", "沟通", "跨部门"]):
        specialty_tags.append("跨部门协调")
    if not specialty_tags:
        # 根据岗位推断默认特长
        if "后端" in " ".join(pos_tags):
            specialty_tags.extend(["技术攻坚", "架构设计"])
        elif "产品" in " ".join(pos_tags):
            specialty_tags.extend(["产品规划", "业务理解"])
        elif "数据" in " ".join(pos_tags):
            specialty_tags.extend(["数据分析", "业务理解"])
        else:
            specialty_tags.extend(["执行力强", "学习能力强"])
    result["specialty"] = specialty_tags[:5]

    # --- 8. 行业经验 ---
    industry_tags = []
    for name, cat, sub in SEED_TAGS:
        if cat != "industry":
            continue
        short = name.replace("行业", "")
        if short.lower() in full_text or short in company:
            industry_tags.append(name)
    if not industry_tags:
        # 从公司名/经历中推断
        if any(k in full_text for k in ["金融", "银行", "证券", "保险"]):
            industry_tags.append("金融行业")
        elif any(k in full_text for k in ["电商", "淘宝", "京东", "拼多多"]):
            industry_tags.append("电商行业")
        elif any(k in full_text for k in ["制造", "工厂", "工业", "汽车"]):
            industry_tags.append("制造业")
        elif any(k in full_text for k in ["互联网", "字节", "腾讯", "阿里", "百度", "美团"]):
            industry_tags.append("互联网行业")
        elif any(k in full_text for k in ["政务", "政府", "国企", "央企"]):
            industry_tags.append("政企行业")
    result["industry"] = industry_tags[:3]

    return result


def _classify_tags(tags: list[str]) -> dict[str, float]:
    """简单按标签是否在内置库推断置信度（演示用，真实可接模型打分）。"""
    known = {name for name, _, _ in SEED_TAGS}
    return {name: (0.9 if name in known else 0.6) for name in tags}


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


# ---------------- 语义化检索 v2（需求④ NLU+结构化过滤+向量精排）----------------
# 袁文武 2026-09-03：重构语义搜索，新增 NLU 解析、结构化过滤、匹配解释、三级降级
from app.services.talent_nlu import parse_query, SearchIntent
from sqlalchemy import or_, select


def semantic_search(db: Session, query: str, top_k: int = 10,
                    use_vector: bool = True) -> list[SemanticSearchHit]:
    """语义搜索 v2：NLU 解析 → 结构化过滤 → 向量/关键词排序 → 匹配解释。

    三级降级：
      L1: LLM NLU → 结构化过滤 → 向量精排（最佳）
      L2: 规则 NLU → 结构化过滤 → 关键词排序（无 LLM 时）
      L3: 多关键词 LIKE 匹配（兜底）
    """
    result = semantic_search_v2(db, query=query, top_k=top_k, use_vector=use_vector)
    # 兼容旧接口：返回 SemanticSearchHit 列表
    hits = []
    for r in result.get("results", []):
        hits.append(SemanticSearchHit(
            talent_id=r["talent_id"],
            name=r["name"],
            score=r.get("score"),
            match_reason=r.get("match_reason", ""),
            snippet=r.get("snippet", ""),
        ))
    return hits


def semantic_search_v2(db: Session, query: str, top_k: int = 10,
                       use_vector: bool = True, use_llm_nlu: bool = True) -> dict:
    """语义搜索 v2 完整结果，含解析信息、匹配条件等。"""
    # 第 1 步：NLU 解析
    intent = parse_query(query, prefer_llm=use_llm_nlu)

    # 第 2 步：结构化过滤
    candidates = _structured_filter_v2(db, intent)

    # 软降级：等级过滤 0 结果时放宽
    relaxed_level = False
    if not candidates and intent.level:
        intent_no_level = SearchIntent(
            raw_query=intent.raw_query,
            years_min=intent.years_min, years_max=intent.years_max,
            education=intent.education, education_min=intent.education_min,
            level=None,
            keywords=list(intent.keywords),
            position_keywords=list(intent.position_keywords),
            industry_keywords=list(intent.industry_keywords),
            parse_mode=intent.parse_mode,
            parsed_conditions=[c for c in intent.parsed_conditions if "等级" not in c],
        )
        candidates = _structured_filter_v2(db, intent_no_level)
        if candidates:
            relaxed_level = True
            intent = intent_no_level

    if not candidates:
        return {
            "query": query, "parse_mode": intent.parse_mode,
            "parsed_conditions": intent.parsed_conditions,
            "search_mode": "structured_filter_no_result",
            "total": 0, "results": [],
            "relaxed": [],
        }

    # 第 3 步：排序
    results = _rank_candidates_v2(db, intent, candidates, top_k, use_vector)

    return {
        "query": query, "parse_mode": intent.parse_mode,
        "parsed_conditions": intent.parsed_conditions,
        "search_mode": results[0].search_mode if results else "none",
        "total": len(results),
        "results": [_result_to_dict(r) for r in results[:top_k]],
        "relaxed": ["已放宽等级条件，按关键词匹配排序"] if relaxed_level else [],
    }


def _structured_filter_v2(db: Session, intent: SearchIntent) -> list:
    """根据 NLU 解析的结构化条件过滤候选人才。"""
    from app.models.talent import Talent, TalentTalentTag, TalentTag
    query = db.query(Talent).filter(Talent.status == 1)

    if intent.years_min is not None:
        query = query.filter(Talent.years_experience >= intent.years_min)
    if intent.years_max is not None:
        query = query.filter(Talent.years_experience <= intent.years_max)

    if intent.education:
        query = query.filter(Talent.highest_education == intent.education)

    if intent.education_min:
        edu_list = _edu_above_v2(intent.education_min)
        query = query.filter(Talent.highest_education.in_(edu_list))

    if intent.level:
        level_subq = (
            select(TalentTalentTag.talent_id)
            .join(TalentTag, TalentTag.id == TalentTalentTag.tag_id)
            .where(TalentTag.category == "level", TalentTag.name == intent.level)
        )
        query = query.filter(Talent.id.in_(level_subq))

    keywords = intent.all_keywords()
    if keywords:
        or_conditions = []
        # 对关键词做扩展：长词拆成短词（如"前端开发"→"前端"），提高召回率
        expanded_kws = _expand_keywords(keywords)
        for kw in list(dict.fromkeys(expanded_kws))[:8]:  # 去重，最多8个
            like = f"%{kw}%"
            or_conditions.append(Talent.skills.like(like))
            or_conditions.append(Talent.work_experience.like(like))
            or_conditions.append(Talent.project_experience.like(like))
            or_conditions.append(Talent.current_title.like(like))
            or_conditions.append(Talent.name.like(like))
        if or_conditions:
            query = query.filter(or_(*or_conditions))

    candidates = query.order_by(Talent.id.desc()).limit(200).all()
    return list(candidates)


def _edu_above_v2(edu_min: str) -> list[str]:
    order = ["大专", "本科", "硕士", "博士"]
    try:
        idx = order.index(edu_min)
    except ValueError:
        return [edu_min]
    return order[idx:]


def _expand_keywords(keywords: list[str]) -> list[str]:
    """扩展关键词列表，提高召回率。

    策略：
    1. 原词保留
    2. 4字以上中文短语拆成2字词（如"前端开发"→"前端"）
    3. 去除纯停用词
    """
    expanded = list(keywords)  # 原词优先
    stop = {"开发", "工程师", "经验", "相关", "方向", "领域", "技术", "项目"}
    for kw in keywords:
        if len(kw) >= 4 and all('\u4e00' <= c <= '\u9fff' for c in kw):
            # 中文长词：尝试前2字
            prefix = kw[:2]
            if prefix not in stop and prefix not in expanded:
                expanded.append(prefix)
            # 尝试后2字
            suffix = kw[-2:]
            if suffix not in stop and suffix not in expanded:
                expanded.append(suffix)
    return expanded


class _SearchResult:
    def __init__(self, talent_id, name, score=None, match_reason="", snippet="",
                 matched_conditions=None, matched_keywords=None, search_mode="keyword", talent=None):
        self.talent_id = talent_id
        self.name = name
        self.score = score
        self.match_reason = match_reason
        self.snippet = snippet
        self.matched_conditions = matched_conditions or []
        self.matched_keywords = matched_keywords or []
        self.search_mode = search_mode
        self.talent = talent


def _result_to_dict(r: _SearchResult) -> dict:
    return {
        "talent_id": r.talent_id, "name": r.name, "score": r.score,
        "match_reason": r.match_reason, "snippet": r.snippet,
        "matched_conditions": r.matched_conditions,
        "matched_keywords": r.matched_keywords,
        "search_mode": r.search_mode,
        "current_title": r.talent.current_title if r.talent else None,
        "current_company": r.talent.current_company if r.talent else None,
        "highest_education": r.talent.highest_education if r.talent else None,
        "years_experience": r.talent.years_experience if r.talent else None,
        "skills": r.talent.skills if r.talent else None,
    }


def _rank_candidates_v2(db: Session, intent: SearchIntent, candidates: list,
                        top_k: int, use_vector: bool) -> list[_SearchResult]:
    if use_vector and intent.has_keywords():
        vector_results = _vector_rank_v2(intent, candidates, top_k)
        if vector_results:
            for r in vector_results:
                _enrich_match_reason_v2(r, intent, r.talent)
            return vector_results
    keyword_results = _keyword_rank_v2(intent, candidates, top_k)
    for r in keyword_results:
        _enrich_match_reason_v2(r, intent, r.talent)
    return keyword_results


def _vector_rank_v2(intent: SearchIntent, candidates: list, top_k: int) -> list[_SearchResult]:
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
        vec = _vec_store()
        query_text = " ".join(intent.all_keywords()) or intent.raw_query
        qv = llm.embed(query_text)
        candidate_ids = {t.id for t in candidates}
        candidate_map = {t.id: t for t in candidates}
        score_map: dict[int, float] = {}
        snippet_map: dict[int, str] = {}
        for key in _VECTOR_SETS:
            if not vec.has_collection(key):
                continue
            try:
                hits = vec.search(key, qv, top_k=min(50, len(candidates) * 2))
                for h in hits:
                    tid = _parse_tid(h.get("text", ""))
                    if tid is None or tid not in candidate_ids:
                        continue
                    score = float(h.get("score", 0))
                    if tid not in score_map or score > score_map[tid]:
                        score_map[tid] = score
                        snippet_map[tid] = h.get("text", "")
            except Exception:
                continue
        if not score_map:
            return []
        sorted_ids = sorted(score_map.keys(), key=lambda x: score_map[x], reverse=True)
        results = []
        for tid in sorted_ids[:top_k]:
            t = candidate_map.get(tid)
            if not t:
                continue
            results.append(_SearchResult(
                talent_id=tid, name=t.name, score=score_map[tid],
                snippet=snippet_map.get(tid, "")[:200], search_mode="vector", talent=t,
            ))
        return results
    except Exception:
        return []


def _keyword_rank_v2(intent: SearchIntent, candidates: list, top_k: int) -> list[_SearchResult]:
    keywords = intent.all_keywords()
    if not keywords:
        sorted_candidates = sorted(candidates, key=lambda t: t.id, reverse=True)
        return [_SearchResult(
            talent_id=t.id, name=t.name, score=None,
            match_reason="结构化条件匹配", search_mode="keyword", talent=t,
        ) for t in sorted_candidates[:top_k]]

    scored = []
    for t in candidates:
        score = 0.0
        matched_kws = []
        search_text = " ".join(filter(None, [
            t.name or "", t.skills or "", t.current_title or "",
            t.work_experience or "", t.project_experience or "",
            t.description or "", t.tags_summary or "",
        ])).lower()
        for kw in keywords:
            if kw.lower() in search_text:
                matched_kws.append(kw)
                if t.skills and kw.lower() in t.skills.lower():
                    score += 2.0
                elif t.current_title and kw.lower() in t.current_title.lower():
                    score += 1.5
                else:
                    score += 1.0
        if intent.years_min is not None and t.years_experience and t.years_experience >= intent.years_min:
            score += 0.5
        if intent.level:
            score += 1.0
        if intent.education or intent.education_min:
            score += 0.5
        scored.append((t, score, matched_kws))
    scored.sort(key=lambda x: x[1], reverse=True)
    results = []
    for t, score, matched_kws in scored[:top_k]:
        results.append(_SearchResult(
            talent_id=t.id, name=t.name,
            score=score if matched_kws else None,
            matched_keywords=matched_kws, search_mode="keyword", talent=t,
        ))
    return results


def _enrich_match_reason_v2(result: _SearchResult, intent: SearchIntent, talent):
    reasons = []
    conditions = []
    if intent.years_min is not None and talent and talent.years_experience is not None:
        if talent.years_experience >= intent.years_min:
            reasons.append(f"年限 {talent.years_experience} 年 ≥ {intent.years_min} 年")
            conditions.append(f"年限符合({talent.years_experience}年)")
    if intent.education and talent and talent.highest_education == intent.education:
        reasons.append(f"学历 {talent.highest_education}")
        conditions.append(f"学历匹配({talent.highest_education})")
    elif intent.education_min and talent and talent.highest_education:
        reasons.append(f"学历 {talent.highest_education}（≥{intent.education_min}）")
        conditions.append(f"学历达标({talent.highest_education})")
    if intent.level:
        reasons.append(f"{intent.level}等级")
        conditions.append(f"等级匹配({intent.level})")
    if result.matched_keywords:
        kw_text = "、".join(result.matched_keywords[:5])
        reasons.append(f"关键词命中：{kw_text}")
        conditions.extend(result.matched_keywords[:5])
    if result.search_mode == "vector" and result.score is not None:
        pct = int(min(100, result.score * 100))
        reasons.append(f"语义相似度 {pct}%")
    if not reasons:
        reasons.append("结构化条件匹配")
    result.match_reason = "；".join(reasons)
    result.matched_conditions = conditions
    result.snippet = result.snippet or _build_snippet_v2(talent, result.matched_keywords)


def _build_snippet_v2(talent, keywords: list[str]) -> str:
    if not talent:
        return ""
    texts = [
        ("技能", talent.skills),
        ("职位", talent.current_title),
        ("工作经历", talent.work_experience),
        ("项目经验", talent.project_experience),
        ("简介", talent.description),
    ]
    snippets = []
    for label, text in texts:
        if not text:
            continue
        for kw in keywords:
            idx = text.lower().find(kw.lower())
            if idx >= 0:
                start = max(0, idx - 20)
                end = min(len(text), idx + len(kw) + 50)
                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                snippets.append(f"【{label}】{snippet}")
                break
        if len(snippets) >= 2:
            break
    return " ".join(snippets) if snippets else (talent.skills or "")[:200]


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
            _ensure_ai_report_three_fields(db, t)
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
