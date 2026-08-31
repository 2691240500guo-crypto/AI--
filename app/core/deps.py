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
    return perms


def require_permission(perm: str):
    """接口鉴权装饰依赖：需持有 perm 权限码；超管放行。"""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.is_super:
            return user
        if perm not in _user_perms(user):
            raise HTTPException(403, f"权限不足：需要 {perm}")
        return user
    return checker


# 便捷引用
get_current_superuser = require_permission("")  # 占位，实际鸭子类型在函数内判断