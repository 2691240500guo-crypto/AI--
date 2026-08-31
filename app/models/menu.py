from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Menu(Base):
    """菜单 + 按钮级权限码（A06）。type：1目录 2菜单 3按钮。"""
    __tablename__ = "sys_menu"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(default=0)
    title: Mapped[str] = mapped_column(String(64))
    icon: Mapped[str | None] = mapped_column(String(64), default=None)
    path: Mapped[str | None] = mapped_column(String(128), default=None)      # 路由，如 /talent
    component: Mapped[str | None] = mapped_column(String(128), default=None) # 视图组件名
    perm: Mapped[str | None] = mapped_column(String(128), default=None)      # 权限码，如 talent:list
    type: Mapped[int] = mapped_column(default=2)                # 1目录 2菜单 3按钮
    sort: Mapped[int] = mapped_column(default=0)
    status: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)