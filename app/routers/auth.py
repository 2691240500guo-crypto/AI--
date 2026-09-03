"""认证路由（A01/A02/A03）。"""
from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import cache_authenticated_user, get_current_user, oauth2_scheme
from app.core.config import get_settings
from app.core.redis_client import enforce_rate_limit, get_redis_service
from app.core.security import revoke_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit import client_ip
from app.services.auth import AuthService
from app.utils.masking import mask_email, mask_phone
from app.utils.response import ok

router = APIRouter()


def _request_ip(request: Request | None) -> str | None:
    return client_ip(request) if request is not None else None


def _login_rate_identity(request: Request | None, username: str) -> str:
    return f"{_request_ip(request) or 'unknown'}|{username.strip().lower()}"


def _self_out(user: User) -> UserOut:
    """当前用户信息脱敏输出：超管明文，其余 phone/email 打码（I03）。"""
    out = UserOut.model_validate(user)
    if not user.is_super:
        out.phone = mask_phone(out.phone)
        out.email = mask_email(out.email)
    return out


@router.post("/login", response_model=None)
def login(body: LoginRequest, db: Session = Depends(get_db), request: Request = None):
    settings = get_settings()
    identity = _login_rate_identity(request, body.username)
    enforce_rate_limit(
        "admin-login",
        identity,
        limit=settings.REDIS_LOGIN_RATE_LIMIT,
        window=settings.REDIS_LOGIN_RATE_WINDOW,
    )
    user, at, rt = AuthService.login(db, body.username, body.password, ip=_request_ip(request))
    db.commit()  # 提交登录日志与 last_login_at（AuthService 内仅 flush）
    cache_authenticated_user(user)
    get_redis_service().clear_rate_limit("admin-login", identity)
    # 避免响应里带密码；手机号/邮箱按角色脱敏
    return ok({"access_token": at, "refresh_token": rt, "user": _self_out(user)})


@router.post("/employee-login", response_model=None)
def employee_login(body: LoginRequest, db: Session = Depends(get_db), request: Request = None):
    """员工小程序登录（A01 分流）：仅 user_type=employee + 角色=employee 可登录，签发 app 端 token。"""
    settings = get_settings()
    identity = _login_rate_identity(request, body.username)
    enforce_rate_limit(
        "employee-login",
        identity,
        limit=settings.REDIS_LOGIN_RATE_LIMIT,
        window=settings.REDIS_LOGIN_RATE_WINDOW,
    )
    user, at, rt = AuthService.employee_login(db, body.username, body.password, ip=_request_ip(request))
    db.commit()
    cache_authenticated_user(user)
    get_redis_service().clear_rate_limit("employee-login", identity)
    return ok({"access_token": at, "refresh_token": rt, "user": _self_out(user)})


@router.post("/refresh")
def refresh(body: dict, db: Session = Depends(get_db)):
    at, rt = AuthService.refresh(db, body["refresh_token"])
    return ok({"access_token": at, "refresh_token": rt})


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """当前登录用户信息（前端硬刷新后恢复右上角昵称等）。"""
    return ok(_self_out(user))


@router.post("/logout")
def logout(
    body: dict | None = Body(default=None),
    token: str | None = Depends(oauth2_scheme),
):
    revoke_token(token)
    revoke_token((body or {}).get("refresh_token"))
    return ok()


@router.post("/wechat")
def wechat(body: dict, db: Session = Depends(get_db)):
    """A03 微信授权登录：入参 {code}，静默换取 openid 后绑定。"""
    code = body.get("code")
    # 本期对接测试：由前端直接传 openid（正式接入微信 code2session）
    openid = body.get("openid") or (f"test_{code}" if code else "")
    user = AuthService.wechat_login(db, openid)
    at, rt, *_ = create_pair(user)
    cache_authenticated_user(user)
    return ok({"access_token": at, "refresh_token": rt, "user": _self_out(user)})


def create_pair(user):
    from app.core.security import create_access_token, create_refresh_token
    return create_access_token(str(user.id)), create_refresh_token(str(user.id)), None
