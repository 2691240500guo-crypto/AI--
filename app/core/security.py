"""密码哈希与 JWT 签发/校验。
修改人：袁文武
修改时间：2026-09-02
说明：直接使用 bcrypt 原生接口，避免 passlib.CryptContext 初始化时的
      detect_wrap_bug 与新版 bcrypt 的 72 字节兼容性问题。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    """生成 bcrypt 密码哈希。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证 bcrypt 密码哈希。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta,
                 client_type: str = "admin") -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject, "type": token_type,
        "exp": now + expires_delta, "iat": now,
        "client_type": client_type,
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
