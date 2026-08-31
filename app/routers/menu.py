"""菜单/权限码路由（A06）与当前用户菜单。

注意：/menus/mine 是所有登录用户获取自己菜单的接口，
不能挂在 require_permission("system:menu") 之下（普通用户无此权限会 403），
因此拆成两个 router：mine 只需登录，CRUD 才需要 system:menu。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.dao.menu import MenuDAO
from app.models.menu import Menu
from app.models.user import User
from app.schemas.role import MenuCreate, MenuOut
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:menu"))])

# 当前用户菜单：仅需登录，无 router 级权限要求
mine_router = APIRouter()


@mine_router.get("/menus/mine")
def my_menus(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前用户可见菜单（前端路由/侧栏依据）。

    若用户只勾选了子菜单（未勾父目录），自动补全所有被勾菜单的父级目录，
    保证侧边栏能渲染出折叠面板（前端按 parent_id 嵌套）。
    """
    perms: set[str] = set()
    if user.is_super:
        menus = MenuDAO.list(db, limit=500, order_by=Menu.sort)
        perms = {m.perm for m in menus if m.perm}
    else:
        seen: dict[int, Menu] = {}
        for role in user.roles:
            for m in role.menus:
                seen[m.id] = m
                if m.perm:
                    perms.add(m.perm)
        menus = sorted(seen.values(), key=lambda x: x.sort)
        # 自动补全父级目录：用户只勾子菜单时也能渲染
        all_menus = MenuDAO.list(db, limit=500, order_by=Menu.sort)
        seen_ids = {m.id for m in menus}
        for m in menus:
            if m.parent_id > 0 and m.parent_id not in seen_ids:
                # 找祖先链（递归）
                pid = m.parent_id
                while pid > 0 and pid not in seen_ids:
                    parent = next((x for x in all_menus if x.id == pid), None)
                    if parent:
                        seen[parent.id] = parent
                        seen_ids.add(parent.id)
                        pid = parent.parent_id
                    else:
                        break
        menus = sorted(seen.values(), key=lambda x: x.sort)
    return ok({"menus": [MenuOut.model_validate(m) for m in menus], "perms": sorted(perms)})


@router.get("")
def list_menus(db: Session = Depends(get_db)):
    rows = MenuDAO.list(db, limit=500, order_by=Menu.sort)
    return ok([MenuOut.model_validate(m) for m in rows])


@router.post("")
def create_menu(body: MenuCreate, db: Session = Depends(get_db)):
    obj = MenuDAO.create(db, **body.model_dump())
    db.commit()
    return ok(MenuOut.model_validate(obj))


@router.put("/{mid}")
def update_menu(mid: int, body: MenuCreate, db: Session = Depends(get_db)):
    m = MenuDAO.get(db, mid)
    if not m:
        raise HTTPException(404, "菜单不存在")
    MenuDAO.update(db, m, **body.model_dump())
    db.commit()
    return ok(MenuOut.model_validate(m))


@router.delete("/{mid}")
def delete_menu(mid: int, db: Session = Depends(get_db)):
    m = MenuDAO.get(db, mid)
    if not m:
        raise HTTPException(404, "菜单不存在")
    MenuDAO.delete(db, m)
    db.commit()
    return ok()