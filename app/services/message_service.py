"""消息服务（H01-H04）。业务只需调用 notify() 一行即可推送。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.message import Message


class MessageService:
    __model__ = Message

    @classmethod
    def send(cls, db: Session, *, type_code: str, title: str, content: str = "",
             sender_id: int | None = None, receiver_ids: list[int] | None = None,
             biz_type: str | None = None, biz_id: int | None = None,
             push_miniapp: int = 0) -> Message:
        """发一条消息。receiver_ids 为空表示全员。"""
        msg = Message(
            type_code=type_code, title=title, content=content, sender_id=sender_id,
            receiver_ids=",".join(map(str, receiver_ids)) if receiver_ids else "0",
            biz_type=biz_type, biz_id=biz_id, push_miniapp=push_miniapp,
        )
        db.add(msg)
        db.flush()
        # H04：若要求推小程序，此处接入订阅消息/模板消息
        if push_miniapp:
            cls._push_miniapp(msg)
        return msg

    @classmethod
    def for_user(cls, db: Session, user_id: int, page: int = 1, page_size: int = 20,
                 unread_only: bool = False) -> tuple[list[Message], int]:
        uid = str(user_id)
        base = (Message.receiver_ids == "0") | (Message.receiver_ids.contains(uid))
        total = db.scalar(select(func.count()).select_from(Message).where(base)) or 0
        stmt = select(Message).where(base).order_by(Message.id.desc())
        if unread_only:
            stmt = stmt.where(~Message.read_ids.contains(uid))
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
        return rows, total

    @classmethod
    def mark_read(cls, db: Session, msg: Message, user_id: int) -> None:
        uid = str(user_id)
        if uid not in [s for s in (msg.read_ids or "").split(",") if s]:
            msg.read_ids = ",".join(filter(bool, [msg.read_ids, uid]))
            db.flush()

    @staticmethod
    def _push_miniapp(msg: Message) -> None:
        # 二期接入小程序订阅消息；本期留桩
        pass