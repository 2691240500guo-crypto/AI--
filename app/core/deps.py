"""FastAPI 依赖：当前用户、鉴权、权限码校验（RBAC，A05/A06）。"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.dao.user import UserDAO
from app.models.menu import Menu
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(db: Session = Depends(get_db),
                     token: str | None = Depends(oauth2_scheme)) -> User:
    credentials_error = HTTPException(401, "未登录或登录已过期")
    if not token:
        raise credentials_error
    payload = decode_token(token)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        raise credentials_error
    user = UserDAO.get(db, int(payload["sub"]))
    if not user or user.status != 1:
        raise credentials_error
    return user


def _user_perms(user: User) -> set[str]:
    perms: set[str] = set()
    for role in user.roles:
        for menu in role.menus:
            if menu.perm:
                perms.add(menu.perm)
                if ":" in menu.perm:
                    perms.add(menu.perm.split(":", 1)[0] + ":*")
    return perms


def _has_perm(required: str, owned: set[str]) -> bool:
    if required in owned:
        return True
    if ":" in required:
        head = required.split(":", 1)[0]
        return f"{head}:*" in owned
    return "*" in owned


def require_permission(perm: str):
    """接口鉴权装饰依赖：需持有 perm 权限码；超管放行。"""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.is_super:
            return user
        if not _has_perm(perm, _user_perms(user)):
            raise HTTPException(403, f"权限不足：需要 {perm}")
        return user
    return checker


def require_any_perm(*perms: str):
    """接口鉴权：持有任一 perm 即通过（超管放行）。

    用于"模块入口"场景：菜单按钮 perm 细粒度（training:course/plan/effect），
    但 router 级保护想用"任一细粒度 perm 即放行"，避免菜单 perm 与路由 perm 字面值不一致。
    """
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.is_super:
            return user
        user_perms = _user_perms(user)
        if not any(p in user_perms for p in perms):
            raise HTTPException(403, f"权限不足：需要 {'/'.join(perms)} 之一")
        return user
    return checker


def _token_client_type(token: str | None) -> str:
    """从 access token 中读端标识；缺省按 admin（兼容旧 token）。"""
    if not token:
        return "admin"
    payload = decode_token(token)
    return (payload or {}).get("client_type") or "admin"


def require_client(types: str | list[str]):
    """端隔离校验器：要求 token 的 client_type ∈ types（如 admin / app）。

    用法：
        _=Depends(require_client("app"))            # 仅小程序
        _=Depends(require_client(["admin", "app"])) # 两端都行
    """
    allowed = {types} if isinstance(types, str) else set(types)
    def checker(request: Request, token: str | None = Depends(oauth2_scheme),
                user: User = Depends(get_current_user)) -> User:
        if _token_client_type(token) not in allowed:
            raise HTTPException(403, "跨端调用被拒绝：token 端标识不匹配")
        return user
    return checker


# 便捷引用
get_current_superuser = require_permission("")  # 占位，实际鸭子类型在函数内判断