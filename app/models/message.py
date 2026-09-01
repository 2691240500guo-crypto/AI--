from datetime import datetime
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    """消息中心（H01-H04）。一条消息可被多人接收（receiver 用逗号分隔暂存，二期可拆表）。"""
    __tablename__ = "msg_center"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type_code: Mapped[str] = mapped_column(String(32), default="system", index=True)  # system/assess/train/approve
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(String(2000), default="")
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), default=None)
    receiver_ids: Mapped[str] = mapped_column(String(500), default="")  # "1,2,3"；0=全员
    read_ids: Mapped[str] = mapped_column(String(500), default="")     # 已读者 id，逗号分隔（H02）
    biz_type: Mapped[str | None] = mapped_column(String(64), default=None)  # 关联业务类型
    biz_id: Mapped[int | None] = mapped_column(default=None)    # 关联业务主键
    push_miniapp: Mapped[int] = mapped_column(default=0)   # 1已推小程序（H04）
    status: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)