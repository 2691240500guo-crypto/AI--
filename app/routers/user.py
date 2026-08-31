"""用户路由（A04）。示例：如何用 BaseDAO + service + 分页。"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.dao.user import UserDAO
from app.schemas.user import (UserCreate, UserOut, UserQuery, UserUpdate)
from app.services.audit import client_ip
from app.services.auth import UserService
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:user"))])


@router.get("")
def list_users(keyword: str | None = None, dept_id: int | None = None,
               status: int | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    total = UserDAO.count(db, keyword, dept_id, status)
    rows = UserDAO.paged(db, keyword, dept_id, status, page, page_size)
    return ok(paged_result([UserOut.model_validate(u) for u in rows], page, page_size, total))


@router.get("/{uid}")
def get_user(uid: int, db: Session = Depends(get_db)):
    u = UserDAO.get(db, uid)
    if not u:
        raise HTTPException(404, "用户不存在")
    return ok(UserOut.model_validate(u))


@router.post("")
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    u = UserService.create(db, body)
    db.commit()
    return ok(UserOut.model_validate(u))


@router.put("/{uid}")
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db)):
    u = UserDAO.get(db, uid)
    if not u:
        raise HTTPException(404, "用户不存在")
    u = UserService.update(db, u, body)
    db.commit()
    return ok(UserOut.model_validate(u))


@router.delete("/{uid}")
def delete_user(uid: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    if uid == current.id:
        raise HTTPException(400, "不能删除自己")
    UserService.delete(db, uid)
    db.commit()
    return ok()