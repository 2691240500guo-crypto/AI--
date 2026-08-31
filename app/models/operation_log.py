from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationLog(Base):
    """操作留痕（A08 / I01），全局中间件写入。"""
    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(default=None, index=True)
    username: Mapped[str | None] = mapped_column(String(64), default=None)
    method: Mapped[str] = mapped_column(String(16), default="")
    path: Mapped[str] = mapped_column(String(255), default="", index=True)
    action: Mapped[str] = mapped_column(String(128), default="")      # 语义动作，如 talent:create
    status_code: Mapped[int] = mapped_column(default=0)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    duration_ms: Mapped[int] = mapped_column(default=0)
    request_body: Mapped[str | None] = mapped_column(String(2000), default=None)  # 脱敏后
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)


class LoginLog(Base):
    """登录日志（A09），含异常预警标记。"""
    __tablename__ = "sys_login_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    success: Mapped[int] = mapped_column(default=1)      # 1成功 0失败
    message: Mapped[str | None] = mapped_column(String(255), default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)