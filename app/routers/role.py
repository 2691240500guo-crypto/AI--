"""角色路由（A05 RBAC）。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.dao.role import RoleDAO
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleOut, RoleUpdate
from app.utils.response import BusinessError, ok

router = APIRouter(dependencies=[Depends(require_permission("system:role"))])

MAX = 200

# 内置超管角色 code 保留字（受保护，禁止任何 CRUD / 列表返回）
# 超管身份由 sys_user.is_super=1 决定，不在角色表里——但若历史/外部残留出现此 code
# 角色，API 层硬性拦截，防止 hr 等业务角色误改/误删造成权限体系混乱。
PROTECTED_ROLE_CODES = {"admin", "super_admin"}


def _is_protected(role: Role) -> bool:
    return role.code in PROTECTED_ROLE_CODES


@router.get("")
def list_roles(name: str | None = None, db: Session = Depends(get_db)):
    conds = []
    if name:
        conds.append(Role.name.like(f"%{name}%"))
    rows = RoleDAO.list(db, *conds, limit=MAX, order_by=Role.id)
    # 过滤内置超管角色，不在角色管理界面暴露
    rows = [r for r in rows if r.code not in PROTECTED_ROLE_CODES]
    return ok([RoleOut.model_validate(r) for r in rows])


@router.post("")
def create_role(body: RoleCreate, db: Session = Depends(get_db)):
    if body.code in PROTECTED_ROLE_CODES:
        raise BusinessError(400, f"角色编码 {body.code} 为系统保留字（内置超管角色），不可创建")
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
    if _is_protected(role):
        raise BusinessError(403, f"角色 {role.code} 为内置超管角色，不可编辑")
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
    if _is_protected(role):
        raise BusinessError(403, f"角色 {role.code} 为内置超管角色，不可删除")
    RoleDAO.delete(db, role)
    db.commit()
    return ok()
