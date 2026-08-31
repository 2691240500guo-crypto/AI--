"""消息路由（H01-H04）。"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.dao.message import MessageDAO
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageOut, MessageSend
from app.services.message_service import MessageService
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter()


def _out(msg: Message, user_id: int) -> MessageOut:
    o = MessageOut.model_validate(msg)
    o.is_read = str(user_id) in [s for s in (msg.read_ids or "").split(",") if s]
    return o


@router.get("", dependencies=[Depends(get_current_user)])
def my_messages(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                unread_only: bool = False, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    rows, total = MessageService.for_user(db, user.id, page, page_size, unread_only)
    return ok(paged_result([_out(m, user.id) for m in rows], page, page_size, total))


@router.post("", dependencies=[Depends(get_current_user)])
def send(body: MessageSend, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发送消息（也作为其他模块 notify 的入口）。"""
    msg = MessageService.send(db, type_code=body.type_code, title=body.title,
                              content=body.content, sender_id=user.id,
                              receiver_ids=body.receiver_ids, biz_type=body.biz_type,
                              biz_id=body.biz_id, push_miniapp=body.push_miniapp)
    db.commit()
    return ok(MessageOut.model_validate(msg))


@router.post("/{mid}/read", dependencies=[Depends(get_current_user)])
def mark_read(mid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = MessageDAO.get(db, mid)
    if not m:
        raise HTTPException(404, "消息不存在")
    MessageService.mark_read(db, m, user.id)
    db.commit()
    return ok({})


@router.get("/unread-count", dependencies=[Depends(get_current_user)])
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows, _ = MessageService.for_user(db, user.id, 1, 200)
    unread = sum(1 for m in rows if str(user.id) not in [s for s in (m.read_ids or "").split(",") if s])
    return ok({"unread": unread})