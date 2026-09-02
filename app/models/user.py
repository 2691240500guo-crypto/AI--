from datetime import datetime
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base


class User(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), index=True, unique=True)  # 登录名
    password: Mapped[str] = mapped_column(String(128))                          # 哈希
    nickname: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    email: Mapped[str | None] = mapped_column(String(128), default=None)
    avatar: Mapped[str | None] = mapped_column(String(255), default=None)          # 头像地址(MinIO)
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("sys_dept.id"), default=None)
    status: Mapped[int] = mapped_column(default=1)                    # 1正常 0禁用
    is_super: Mapped[int] = mapped_column(default=0)                  # 1超管(越过权限码)
    openid: Mapped[str | None] = mapped_column(String(64), default=None)          # 微信 openid (A03)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("tal_talent.id"), default=None, index=True)  # 关联人才档案
    user_type: Mapped[str] = mapped_column(String(16), default="admin")            # admin / employee
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    roles = relationship("Role", secondary="sys_user_role", lazy="selectin")

    @validates("username")
    def _strip_username(self, key: str, value: str) -> str:
        return value.strip()


class UserRole(Base):
    __tablename__ = "sys_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id"), primary_key=True)
