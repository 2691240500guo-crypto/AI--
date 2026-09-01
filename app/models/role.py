from datetime import datetime
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)   # 权限码前缀
    name: Mapped[str] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(String(255), default=None)
    status: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    menus = relationship("Menu", secondary="sys_role_menu", lazy="selectin")


class RoleMenu(Base):
    __tablename__ = "sys_role_menu"
    __table_args__ = (UniqueConstraint("role_id", "menu_id"),)

    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id"), primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("sys_menu.id"), primary_key=True)