"""人才档案域 TAL 只读对接模型（对接临时用）。

说明：tal_* 表由人才域同事负责，本文件仅为培训前端对接所需提供
tal_talent 的只读映射（人才下拉 + 计划联查姓名）。
表已存在于云端库，此处不做建表/迁移，字段以云端实际结构为准；
待人才域正式提交模型后，此文件应删除并替换为其官方模型。
"""
from datetime import datetime

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Talent(Base):
    """人才档案主表 tal_talent（只读）。"""
    __tablename__ = "tal_talent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    gender: Mapped[str | None] = mapped_column(String(8), default=None)
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    email: Mapped[str | None] = mapped_column(String(128), default=None)
    highest_education: Mapped[str | None] = mapped_column(String(64), default=None)
    major: Mapped[str | None] = mapped_column(String(128), default=None)
    current_title: Mapped[str | None] = mapped_column(String(128), default=None)
    years_experience: Mapped[int] = mapped_column(default=0)
    skills: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[int] = mapped_column(Integer, default=1)      # 1正常 0已合并/失效
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
