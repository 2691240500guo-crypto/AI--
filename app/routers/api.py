"""统一路由挂载。业务新增模块时在此登记 router，即挂到 /api/v1 之下。"""
from fastapi import APIRouter

from app.routers import auth, user, role, menu, dept, dict_item, message, audit, matching

api = APIRouter()
api.include_router(auth.router, prefix="/auth", tags=["auth"])
api.include_router(user.router, prefix="/users", tags=["user"])
api.include_router(role.router, prefix="/roles", tags=["role"])
api.include_router(menu.router, prefix="/menus", tags=["menu"])
# 当前用户菜单（仅需登录，供所有角色取菜单），路径已在 mine_router 内定义为 /menus/mine
api.include_router(menu.mine_router, tags=["menu"])
api.include_router(dept.router, prefix="/depts", tags=["dept"])
api.include_router(dict_item.router, prefix="/dicts", tags=["dict"])
api.include_router(message.router, prefix="/messages", tags=["message"])
api.include_router(audit.router, prefix="/audit", tags=["audit"])
api.include_router(matching.router, prefix="/matching", tags=["matching"])