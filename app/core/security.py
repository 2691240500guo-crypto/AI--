"""密码哈希与 JWT 签发/校验。"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "exp": now + expires_delta, "iat": now}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    s = get_settings()
    return create_token(subject, "access", timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> str:
    s = get_settings()
    return create_token(subject, "refresh", timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
    except JWTError:
        return None