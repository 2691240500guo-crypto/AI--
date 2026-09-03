"""FastAPI 依赖：当前用户、鉴权、权限码校验（RBAC，A05/A06）。"""
from types import SimpleNamespace

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import get_redis_service
from app.core.security import decode_token, is_token_revoked
from app.db.session import get_db
from app.dao.user import UserDAO
from app.models.menu import Menu
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_USER_CACHE_FIELDS = (
    "id", "username", "nickname", "phone", "email", "avatar", "dept_id",
    "status", "is_super", "openid", "emp_no", "talent_id", "user_type",
    "last_login_at", "created_at", "updated_at",
)
_ROLE_CACHE_FIELDS = ("id", "code", "name", "remark", "status", "created_at")
_MENU_CACHE_FIELDS = (
    "id", "parent_id", "title", "icon", "path", "component", "perm",
    "type", "sort", "status", "created_at",
)


def _cached_value(value):
    """把日期等值转成 Redis JSON 可稳定保存的格式。"""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _user_snapshot(user) -> dict:
    """生成不含密码的鉴权快照，供高频请求绕开远程 MySQL。"""
    roles = []
    for role in user.roles:
        role_data = {field: _cached_value(getattr(role, field, None)) for field in _ROLE_CACHE_FIELDS}
        role_data["menus"] = [
            {field: _cached_value(getattr(menu, field, None)) for field in _MENU_CACHE_FIELDS}
            for menu in role.menus
        ]
        roles.append(role_data)
    snapshot = {field: _cached_value(getattr(user, field, None)) for field in _USER_CACHE_FIELDS}
    snapshot["roles"] = roles
    return snapshot


def _user_from_snapshot(snapshot: dict, expected_id: int):
    """恢复只读用户对象；路由只依赖这些标量属性及角色/菜单集合。"""
    if int(snapshot.get("id", 0)) != expected_id or int(snapshot.get("status", 0)) != 1:
        raise ValueError("invalid cached user")
    roles = []
    for role_data in snapshot.get("roles") or []:
        menus = [SimpleNamespace(**menu) for menu in role_data.get("menus") or []]
        roles.append(SimpleNamespace(
            **{key: value for key, value in role_data.items() if key != "menus"},
            menus=menus,
        ))
    return SimpleNamespace(
        **{key: value for key, value in snapshot.items() if key != "roles"},
        roles=roles,
    )


def cache_authenticated_user(user) -> None:
    """登录或回源成功后预热当前用户、角色和权限快照。"""
    service = get_redis_service()
    if not service.enabled:
        return
    key = service.versioned_key("auth", f"user:{user.id}")
    service.set_json(key, _user_snapshot(user), get_settings().REDIS_AUTH_TTL)


def load_authenticated_user(db: Session, user_id: int):
    """优先从本机 Redis 读取登录态；缓存故障或未命中时回源 MySQL。"""
    service = get_redis_service()
    if service.enabled:
        key = service.versioned_key("auth", f"user:{user_id}")
        cached = service.get_json(key)
        if isinstance(cached, dict):
            try:
                return _user_from_snapshot(cached, user_id)
            except (TypeError, ValueError):
                service.delete(key)

    user = UserDAO.get(db, user_id)
    if user and user.status == 1:
        cache_authenticated_user(user)
    return user


def get_current_user(db: Session = Depends(get_db),
                     token: str | None = Depends(oauth2_scheme)) -> User:
    credentials_error = HTTPException(401, "未登录或登录已过期")
    if not token:
        raise credentials_error
    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "access"
        or not payload.get("sub")
        or is_token_revoked(payload)
    ):
        raise credentials_error
    user = load_authenticated_user(db, int(payload["sub"]))
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
