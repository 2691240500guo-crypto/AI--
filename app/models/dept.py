from datetime import datetime
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dept(Base):
    """部门/组织架构（A07），行级权限来源。"""
    __tablename__ = "sys_dept"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(64))
    leader: Mapped[str | None] = mapped_column(String(64), default=None)
    sort: Mapped[int] = mapped_column(default=0)
    status: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class Position(Base):
    """岗位（S-5 层级）。"""
    __tablename__ = "sys_position"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dept.id"), default=None)
    name: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(default=1)   # 职级