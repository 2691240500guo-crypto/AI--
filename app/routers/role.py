"""角色路由（A05 RBAC）。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.dao.role import RoleDAO
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleOut, RoleUpdate
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:role"))])

MAX = 200


@router.get("")
def list_roles(name: str | None = None, db: Session = Depends(get_db)):
    conds = []
    if name:
        conds.append(Role.name.like(f"%{name}%"))
    rows = RoleDAO.list(db, *conds, limit=MAX, order_by=Role.id)
    return ok([RoleOut.model_validate(r) for r in rows])


@router.post("")
def create_role(body: RoleCreate, db: Session = Depends(get_db)):
    if RoleDAO.get_by(db, code=body.code):
        raise HTTPException(400, "角色编码已存在")
    obj = RoleDAO.create(db, code=body.code, name=body.name, remark=body.remark)
    RoleDAO.set_menus(db, obj.id, body.menu_ids)
    db.commit()
    return ok(RoleOut.model_validate(obj))


@router.put("/{rid}")
def update_role(rid: int, body: RoleUpdate, db: Session = Depends(get_db)):
    role = RoleDAO.get(db, rid)
    if not role:
        raise HTTPException(404, "角色不存在")
    RoleDAO.update(db, role, name=body.name, remark=body.remark, status=body.status)
    if body.menu_ids is not None:
        RoleDAO.set_menus(db, rid, body.menu_ids)
    db.commit()
    return ok(RoleOut.model_validate(role))


@router.delete("/{rid}")
def delete_role(rid: int, db: Session = Depends(get_db)):
    role = RoleDAO.get(db, rid)
    if not role:
        raise HTTPException(404, "角色不存在")
    RoleDAO.delete(db, role)
    db.commit()
    return ok()
