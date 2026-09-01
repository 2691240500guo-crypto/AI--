"""用户路由（A04）。示例：如何用 BaseDAO + service + 分页。

脱敏（I03）：phone/email 默认脱敏返回（需求：证件号/电话/邮箱默认脱敏返回，is_super 明文）。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.dao.user import UserDAO
from app.models.user import User
from app.schemas.user import (UserCreate, UserOut, UserUpdate)
from app.services.auth import UserService
from app.utils.masking import mask_email, mask_phone
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:user"))])


def _mask_out(user, current: User) -> UserOut:
    """脱敏输出：超管看明文；其余角色 phone/email 打码。"""
    out = UserOut.model_validate(user)
    if not current.is_super:
        out.phone = mask_phone(out.phone)
        out.email = mask_email(out.email)
    return out


@router.get("")
def list_users(keyword: str | None = None, dept_id: int | None = None,
               status: int | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=200),
               current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = UserDAO.count(db, keyword, dept_id, status)
    rows = UserDAO.paged(db, keyword, dept_id, status, page, page_size)
    return ok(paged_result([_mask_out(u, current) for u in rows], page, page_size, total))


@router.get("/{uid}")
def get_user(uid: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = UserDAO.get(db, uid)
    if not u:
        raise HTTPException(404, "用户不存在")
    return ok(_mask_out(u, current))


@router.post("")
def create_user(body: UserCreate, current: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    u = UserService.create(db, body)
    db.commit()
    return ok(_mask_out(u, current))


@router.put("/{uid}")
def update_user(uid: int, body: UserUpdate, current: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    u = UserDAO.get(db, uid)
    if not u:
        raise HTTPException(404, "用户不存在")
    u = UserService.update(db, u, body)
    db.commit()
    return ok(_mask_out(u, current))


@router.delete("/{uid}")
def delete_user(uid: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    if uid == current.id:
        raise HTTPException(400, "不能删除自己")
    UserService.delete(db, uid)
    db.commit()
    return ok()