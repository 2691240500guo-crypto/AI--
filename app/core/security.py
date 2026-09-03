"""密码哈希与 JWT 签发/校验。"""
from datetime import datetime, timedelta, timezone
import time
from typing import Any
from uuid import uuid4

# passlib[bcrypt]==1.7.* 依赖 bcrypt.__about__.__version__ 探测后端版本；
# bcrypt>=4.1 移除了 __about__，会导致 passlib 每次初始化打印
# "(trapped) error reading bcrypt version"（无害但脏日志）。此处按 passlib 官方
# workaround 补齐该属性，保留 passlib 技术栈且日志干净。（2026-09-02 兼容修复）
import bcrypt as _bcrypt
if not hasattr(_bcrypt, "__about__"):
    import types as _types
    _about = _types.ModuleType("bcrypt.__about__")
    _about.__version__ = getattr(_bcrypt, "__version__", "4.1.0")
    _bcrypt.__about__ = _about

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str, token_type: str, expires_delta: timedelta,
                 client_type: str = "admin") -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject, "type": token_type,
        "exp": now + expires_delta, "iat": now,
        "jti": uuid4().hex,
        "client_type": client_type,  # 端标识：admin(管理端) / app(小程序)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, client_type: str = "admin") -> str:
    s = get_settings()
    return create_token(subject, "access", timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES),
                        client_type=client_type)


def create_refresh_token(subject: str, client_type: str = "admin") -> str:
    s = get_settings()
    return create_token(subject, "refresh", timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS),
                        client_type=client_type)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
    except JWTError:
        return None


def is_token_revoked(payload: dict[str, Any]) -> bool:
    from app.core.redis_client import get_redis_service

    return get_redis_service().is_token_blacklisted(payload.get("jti"))


def revoke_token(token: str | None) -> bool:
    if not token:
        return False
    payload = decode_token(token)
    if not payload:
        return False
    expires_at = int(payload.get("exp") or 0)
    ttl = max(0, expires_at - int(time.time()))
    from app.core.redis_client import get_redis_service

    return get_redis_service().blacklist_token(payload.get("jti"), ttl)
