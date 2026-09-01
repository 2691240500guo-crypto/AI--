"""人才档案域 TAL 模型：tal_talent 人才主表（对齐 01-需求分析 3.2）。

说明：字段按需求文档 3.2 tal_talent 表设计 + 云端实际列（40 列）映射；
当前仅映射需求字段与业务引用字段，其余扩展列（如 current_company 等）
按需补充。本域正式模型提交后应替换为本文件。
"""
from datetime import datetime

from sqlalchemy import String, Text, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Talent(Base):
    """人才档案主表 tal_talent（对齐需求文档 3.2）。"""
    __tablename__ = "tal_talent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    gender: Mapped[str | None] = mapped_column(String(8), default=None)
    birth_date: Mapped[datetime | None] = mapped_column(Date, default=None)
    id_card: Mapped[str | None] = mapped_column(String(32), default=None)      # 明文存/脱敏出
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    email: Mapped[str | None] = mapped_column(String(128), default=None)
    avatar: Mapped[str | None] = mapped_column(String(255), default=None)
    dept_id: Mapped[int | None] = mapped_column(Integer, default=None)
    position_id: Mapped[int | None] = mapped_column(Integer, default=None)
    degree: Mapped[str | None] = mapped_column(String(64), default=None)       # 学历（字典）
    school: Mapped[str | None] = mapped_column(String(128), default=None)
    major: Mapped[str | None] = mapped_column(String(128), default=None)
    level: Mapped[str | None] = mapped_column(String(16), default=None)        # 人才等级（字典，Agent②回写 S/A/B/C）
    years_experience: Mapped[int] = mapped_column(default=0)
    tags_summary: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    resume_id: Mapped[str | None] = mapped_column(String(255), default=None)   # MinIO 简历对象
    status: Mapped[int] = mapped_column(Integer, default=1)                    # 1正常 0已合并/失效
    created_by: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)

    # 云端扩展列（既有数据兼容，保留映射）：当前职称/最高学历/技能
    highest_education: Mapped[str | None] = mapped_column(String(64), default=None)
    current_title: Mapped[str | None] = mapped_column(String(128), default=None)
    skills: Mapped[str | None] = mapped_column(Text, default=None)
