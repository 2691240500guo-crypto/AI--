#袁文武新增2026-08-31 17:10:00开始
"""人才档案模块出入参（Pydantic v2）。"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ---------------- 子结构 ----------------
class EducationIn(BaseModel):
    school: str | None = None
    degree: str | None = None
    major: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class WorkIn(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class ProjectIn(BaseModel):
    name: str | None = None
    role: str | None = None
    description: str | None = None


# ---------------- 创建 / 更新 ----------------
class TalentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    id_card: str | None = None
    highest_education: str | None = None
    major: str | None = None
    current_title: str | None = None
    years_experience: int = 0
    salary_expectation: str | None = None
    skills: str | None = None
    work_experience: str | None = None
    project_experience: str | None = None
    honors: str | None = None
    resume_source: str | None = "manual"
    educations: list[EducationIn] = []
    works: list[WorkIn] = []
    projects: list[ProjectIn] = []
    tag_names: list[str] = []  # 手动指定标签（自定义/内置均可）


class TalentUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    id_card: str | None = None
    highest_education: str | None = None
    major: str | None = None
    current_title: str | None = None
    years_experience: int | None = None
    salary_expectation: str | None = None
    skills: str | None = None
    work_experience: str | None = None
    project_experience: str | None = None
    honors: str | None = None
    status: int | None = None
    tag_names: list[str] | None = None


# ---------------- 查询条件 ----------------
class TalentQuery(BaseModel):
    keyword: str | None = None           # 姓名/技能/经历模糊
    tag: str | None = None               # 标签名精确
    education: str | None = None         # 学历
    skill: str | None = None             # 技能关键词
    years_min: int | None = None         # 从业年限下限
    level: str | None = None             # 能力等级标签（如 高级/骨干）
    page: int = 1
    page_size: int = 20


# ---------------- 输出 ----------------
class TagOut(ORMModel):
    id: int
    name: str
    category: str
    description: str | None = None
    is_builtin: int = 0
    score: float | None = None           # 仅人才维度返回时携带


class EducationOut(ORMModel):
    id: int
    school: str | None = None
    degree: str | None = None
    major: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class WorkOut(ORMModel):
    id: int
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class ProjectOut(ORMModel):
    id: int
    name: str | None = None
    role: str | None = None
    description: str | None = None

class CertificateOut(ORMModel):
    id: int
    name: str
    issuer: str | None = None
    cert_no: str | None = None
    issue_date: str | None = None
    expire_date: str | None = None
    level: str | None = None
    description: str | None = None

class TalentOut(ORMModel):
    id: int
    name: str
    # 管理端业务选择器使用的人才 ↔ 可登录员工账号映射。
    # 无有效员工账号时保持为空，调用方可展示但应禁止选择。
    user_id: int | None = None
    username: str | None = None
    nickname: str | None = None
    gender: str | None = None
    phone_masked: str | None = None      # 脱敏手机号
    phone: str | None = None             # hq+ 原始手机号
    email: str | None = None
    # hq+ 合并补充字段（tal_talent ALTER 加）
    birth_year: int | None = None
    current_company: str | None = None
    summary: str | None = None
    object_key: str | None = None
    resume_text: str | None = None
    # hq+ 需求分析 01-需求分析.md T 域字段对齐
    id_card: str | None = None
    birth_date: date | None = None
    avatar: str | None = None
    dept_id: int | None = None
    position_id: int | None = None
    degree: str | None = None
    school: str | None = None
    level: str | None = None
    tags_summary: str | None = None
    description: str | None = None
    resume_id: str | None = None
    created_by: int | None = None
    highest_education: str | None = None
    major: str | None = None
    current_title: str | None = None
    years_experience: int = 0
    salary_expectation: str | None = None
    skills: str | None = None
    work_experience: str | None = None
    project_experience: str | None = None
    honors: str | None = None
    resume_source: str | None = None
    resume_file: str | None = None
    status: int = 1
    data_quality: str | None = None
    quality_remark: str | None = None
    expire_at: datetime | None = None
    tags: list[TagOut] = []
    educations: list[EducationOut] = []
    works: list[WorkOut] = []
    projects: list[ProjectOut] = []
    certificates: list[CertificateOut] = []
    created_at: datetime
    updated_at: datetime


# ---------------- 画像 / 检索 / RAG / 治理 ----------------
class TalentProfileOut(BaseModel):
    talent_id: int
    name: str
    vectors_built: bool = False            # 四维向量是否生成
    ai_tags: list[str] = []                 # 全部 AI 标签（扁平列表，兼容旧字段）
    skill_summary: str | None = None
    experience_summary: str | None = None
    quality_summary: str | None = None
    potential_level: str | None = None      # 潜力评级
    # 袁文武 2026-09-03 新增：多维度标签分组 + 元信息
    tags_by_dim: dict[str, list[str]] = {}  # 按维度分组的标签 {skill:[], level:[], ...}
    tag_count: int = 0                      # 标签总数
    generate_mode: str = "rule"             # 生成方式：llm / rule / fast
    profile_updated_at: str | None = None   # 画像更新时间


class SemanticSearchRequest(BaseModel):
    query: str                           # 自然语言，如“擅长数字化转型、3年以上AI项目经验的骨干”
    top_k: int = 10
    use_vector: bool = True              # 是否启用向量语义检索（Milvus 不可用时自动降级关键词）


class SemanticSearchHit(BaseModel):
    talent_id: int
    name: str
    score: float | None = None           # 向量相似度（降级时为 None）
    match_reason: str | None = None      # 命中说明
    snippet: str | None = None


class RAGRequest(BaseModel):
    question: str
    talent_id: int | None = None          # 单人才ID（优先使用）
    talent_ids: list[int] | None = None  # 批量人才ID（为空+无talent_id则全量）
    top_k: int = 5
    scope: str = "batch"                 # single/batch


class RAGResponse(BaseModel):
    question: str
    answer: str
    scope: str
    talents_covered: int = 0


class DuplicateCandidate(BaseModel):
    talent_id: int
    name: str
    reason: str                          # 命中原因：同名/同手机/同邮箱/向量相似
    similarity: float | None = None


class DedupResult(BaseModel):
    talent_id: int
    name: str
    candidates: list[DuplicateCandidate] = []


class MergeRequest(BaseModel):
    primary_id: int                      # 保留的主档案
    duplicate_ids: list[int]             # 待合并（置为失效，指向主档案）


class GovernanceIssue(BaseModel):
    talent_id: int
    name: str
    issue_type: str                      # missing_field/duplicate/suspect
    field: str | None = None
    suggestion: str


# ---------------- 需求④ 导出 / 统计 / Excel 批量导入 / 过期提醒 ----------------
class ExcelImportResult(BaseModel):
    total: int = 0                       # 读取总行数
    imported: int = 0                    # 成功入库条数
    skipped: int = 0                     # 跳过（空行/缺姓名）条数
    errors: list[dict] = []              # 逐行失败明细 [{row, name, error}]


class TalentStatsOut(BaseModel):
    total: int = 0                       # 有效档案总数
    by_education: dict[str, int] = {}    # 学历分布（key=学历，value=人数）
    by_level: dict[str, int] = {}        # 能力等级分布（level 类标签）
    by_skill: dict[str, int] = {}        # 技能标签 TOP 分布
    by_source: dict[str, int] = {}       # 入库来源分布（manual/excel/pdf/docx/image）
    expiring_count: int = 0              # 即将过期/已过期档案数


class ExpiringTalent(BaseModel):
    talent_id: int
    name: str
    expire_at: datetime | None = None
    days_left: int | None = None         # 负数表示已过期
#袁文武新增2026-08-31 17:10:00结束

#袁文武新增2026-08-31 23:30:00开始
# ---------------- 技能证书 ----------------
class CertificateIn(BaseModel):
    name: str
    issuer: str | None = None
    cert_no: str | None = None
    issue_date: str | None = None
    expire_date: str | None = None
    level: str | None = None
    description: str | None = None





# ---------------- 标签管理 CRUD ----------------
class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str = "custom"            # skill/position/level/exp/quality/custom/potential
    description: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None


class TagQuery(BaseModel):
    keyword: str | None = None
    category: str | None = None
    is_builtin: int | None = None
    page: int = 1
    page_size: int = 50


# ---------------- Word 批量导入 ----------------
class WordImportResult(BaseModel):
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[dict] = []
#袁文武新增2026-08-31 23:30:00结束
