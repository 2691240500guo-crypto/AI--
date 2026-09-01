"""人才档案主档（批次1 + 合并袁文武字段）。

本模块为「AI 智能人才档案与数字画像」大模块下的**人才主档** ORM 模型。

2026-09-01 合并说明（hq+）：
- 表名由 ``biz_talent`` 改为云库统一的 ``tal_talent``（团队共享 MySQL adtp_db）
- 字段 = 袁文武 26 字段（id_card/highest_education/major/years_experience/
  salary_expectation/skills/work_experience/project_experience/honors/resume_source/
  resume_file/resume_text/merged_into/data_quality/quality_remark/expire_at/created_by）
  + 我 ALTER 加的 4 字段（object_key/current_company/birth_year/summary）
- 我的旧字段映射：raw_text→resume_text、source→resume_source、education→highest_education、
  years_of_exp→years_experience（前端/代码对应改名）
- ``status``: 1=在档 / 0=失效（软删标记）
- 子表：tal_education / tal_work_experience / tal_project / tal_certificate / tal_resume_parse_log
- 标签：tal_tag（字典）+ tal_talent_tag（关联，含 score）

仅本模块新增，不影响基座其他表。
"""
# hq新增内容 - 人才档案批次1 + 合并
from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Talent(Base):
    """人才主档（tal_talent，云库 30 字段）。"""

    __tablename__ = "tal_talent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 基础信息 ----
    name: Mapped[str] = mapped_column(String(64), index=True, comment="姓名")
    gender: Mapped[str | None] = mapped_column(String(8), default=None, comment="男/女")
    birth_year: Mapped[int | None] = mapped_column(Integer, default=None, comment="出生年（hq+）")
    # hq+  需求分析 01-需求分析.md T 域字段对齐（云库 tal_talent 已有列）
    birth_date: Mapped[date | None] = mapped_column(Date, default=None, comment="出生日期")
    avatar: Mapped[str | None] = mapped_column(String(255), default=None, comment="头像 MinIO")
    phone: Mapped[str | None] = mapped_column(String(20), default=None, index=True, comment="手机号")
    email: Mapped[str | None] = mapped_column(String(128), default=None, comment="邮箱")
    id_card: Mapped[str | None] = mapped_column(String(32), default=None, comment="证件号（加密存储）")
    # hq+  组织归属（需求分析：dept_id/position_id 行级权限来源）
    dept_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="部门 id")
    position_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="岗位 id")

    # ---- 职业/学历信息 ----
    highest_education: Mapped[str | None] = mapped_column(String(64), default=None, comment="最高学历")
    # hq+  需求分析字段：degree（字典）/ school / level（字典，Agent②回写）
    degree: Mapped[str | None] = mapped_column(String(64), default=None, comment="学历（字典）")
    school: Mapped[str | None] = mapped_column(String(128), default=None, comment="毕业院校")
    level: Mapped[str | None] = mapped_column(String(32), default=None, comment="人才等级（字典）")
    major: Mapped[str | None] = mapped_column(String(128), default=None, comment="专业")
    current_title: Mapped[str | None] = mapped_column(String(128), default=None, comment="当前/期望职位")
    current_company: Mapped[str | None] = mapped_column(String(128), default=None, comment="当前公司（hq+）")
    years_experience: Mapped[int] = mapped_column(Integer, default=0, comment="从业年限")
    salary_expectation: Mapped[str | None] = mapped_column(String(64), default=None, comment="薪资期望")

    # ---- 画像与原文 ----
    skills: Mapped[str | None] = mapped_column(Text, default=None, comment="技能摘要文本")
    work_experience: Mapped[str | None] = mapped_column(Text, default=None, comment="工作经历文本")
    project_experience: Mapped[str | None] = mapped_column(Text, default=None, comment="项目经验文本")
    honors: Mapped[str | None] = mapped_column(Text, default=None, comment="荣誉资质")
    summary: Mapped[str | None] = mapped_column(Text, default=None, comment="个人简介（hq+）")
    # hq+  需求分析字段：tags_summary / description
    tags_summary: Mapped[str | None] = mapped_column(String(255), default=None, comment="标签摘要")
    description: Mapped[str | None] = mapped_column(Text, default=None, comment="人才描述")

    # ---- 来源与附件 ----
    resume_source: Mapped[str | None] = mapped_column(String(32), default="manual",
                                                     comment="manual/excel/pdf/docx/image")
    resume_file: Mapped[str | None] = mapped_column(String(255), default=None, comment="MinIO 对象名")
    # hq+  需求分析字段：resume_id（简历文件 MinIO 引用）
    resume_id: Mapped[str | None] = mapped_column(String(255), default=None, comment="简历文件 MinIO 键")
    object_key: Mapped[str | None] = mapped_column(String(256), default=None, index=True,
                                                  comment="MinIO 原始简历对象键（hq+）")
    resume_text: Mapped[str | None] = mapped_column(Text, default=None, comment="简历原文（脱敏留档）")

    # ---- 数据治理/合并/过期 ----
    status: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="1正常/0失效")
    merged_into: Mapped[int | None] = mapped_column(Integer, default=None, comment="查重合并后主档案 id")
    data_quality: Mapped[str | None] = mapped_column(String(16), default="good",
                                                    comment="good/warning/error")
    quality_remark: Mapped[str | None] = mapped_column(String(512), default=None, comment="数据治理整改建议")
    expire_at: Mapped[datetime | None] = mapped_column(default=None, comment="过期提醒时间")
    created_by: Mapped[int | None] = mapped_column(Integer, default=None)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    # ---- 关系 ----
    tag_rels = relationship("TalentTalentTag", back_populates="talent", cascade="all, delete-orphan")
    educations = relationship("TalentEducation", back_populates="talent", cascade="all, delete-orphan")
    works = relationship("TalentWorkExperience", back_populates="talent", cascade="all, delete-orphan")
    projects = relationship("TalentProject", back_populates="talent", cascade="all, delete-orphan")
    certificates = relationship("TalentCertificate", back_populates="talent", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # noqa: D401
        return f"<Talent id={self.id} name={self.name!r}>"


class TalentEducation(Base):
    """教育经历子表（tal_education，袁文武）。"""
    __tablename__ = "tal_education"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True)
    school: Mapped[str | None] = mapped_column(String(128), default=None)
    degree: Mapped[str | None] = mapped_column(String(32), default=None)
    major: Mapped[str | None] = mapped_column(String(128), default=None)
    start_year: Mapped[int | None] = mapped_column(Integer, default=None)
    end_year: Mapped[int | None] = mapped_column(Integer, default=None)
    talent = relationship("Talent", back_populates="educations")


class TalentWorkExperience(Base):
    """工作经历子表（tal_work_experience，袁文武）。"""
    __tablename__ = "tal_work_experience"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True)
    company: Mapped[str | None] = mapped_column(String(128), default=None)
    title: Mapped[str | None] = mapped_column(String(128), default=None)
    start_date: Mapped[str | None] = mapped_column(String(32), default=None)
    end_date: Mapped[str | None] = mapped_column(String(32), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    talent = relationship("Talent", back_populates="works")


class TalentProject(Base):
    """项目经验子表（tal_project，袁文武）。"""
    __tablename__ = "tal_project"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(128), default=None)
    role: Mapped[str | None] = mapped_column(String(64), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    talent = relationship("Talent", back_populates="projects")


class TalentCertificate(Base):
    """技能/资格证书子表（tal_certificate，袁文武）。"""
    __tablename__ = "tal_certificate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), comment="证书名称")
    issuer: Mapped[str | None] = mapped_column(String(128), default=None)
    cert_no: Mapped[str | None] = mapped_column(String(64), default=None)
    issue_date: Mapped[str | None] = mapped_column(String(32), default=None)
    expire_date: Mapped[str | None] = mapped_column(String(32), default=None)
    level: Mapped[str | None] = mapped_column(String(32), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    talent = relationship("Talent", back_populates="certificates")


class TalentTag(Base):
    """标签字典（tal_tag，袁文武：内置 200+ 标签 + 自定义）。"""
    __tablename__ = "tal_tag"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32), default="custom")
    description: Mapped[str | None] = mapped_column(String(255), default=None)
    is_builtin: Mapped[int] = mapped_column(Integer, default=0, comment="1内置/0自定义")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class TalentTalentTag(Base):
    """人才-标签关系（tal_talent_tag，含能力等级/置信度）。"""
    __tablename__ = "tal_talent_tag"
    __table_args__ = (UniqueConstraint("talent_id", "tag_id"),)

    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"),
                                           primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tal_tag.id"), primary_key=True)
    source: Mapped[str | None] = mapped_column(String(16), default="ai", comment="ai/manual")
    score: Mapped[float | None] = mapped_column(Float, default=None, comment="能力等级/置信度")
    talent = relationship("Talent", back_populates="tag_rels")
    tag = relationship("TalentTag")


class TalentResumeParseLog(Base):
    """简历解析日志（tal_resume_parse_log，袁文武）。"""
    __tablename__ = "tal_resume_parse_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("tal_talent.id"), default=None)
    file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    file_type: Mapped[str | None] = mapped_column(String(16), default=None, comment="pdf/docx/image")
    status: Mapped[str] = mapped_column(String(16), default="success", comment="success/failed")
    message: Mapped[str | None] = mapped_column(String(512), default=None)
    parsed_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
