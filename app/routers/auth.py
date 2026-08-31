"""认证路由（A01/A02/A03）。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.schemas.common import LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit import client_ip
from app.services.auth import AuthService
from app.utils.response import ok

router = APIRouter()


@router.post("/login", response_model=None)
def login(body: LoginRequest, db: Session = Depends(get_db), request: Request = None):
    user, at, rt = AuthService.login(db, body.username, body.password, ip=client_ip(request))
    db.commit()  # 提交登录日志与 last_login_at（AuthService 内仅 flush）
    # 避免响应里带密码
    return ok({"access_token": at, "refresh_token": rt, "user": UserOut.model_validate(user)})


@router.post("/refresh")
def refresh(body: dict, db: Session = Depends(get_db)):
    at, rt = AuthService.refresh(db, body["refresh_token"])
    return ok({"access_token": at, "refresh_token": rt})


@router.post("/logout")
def logout(user=Depends(get_current_user)):
    # JWT 无状态，前端清除 token 即可；此处预留黑名单(需 Redis)
    return ok()


@router.post("/wechat")
def wechat(body: dict, db: Session = Depends(get_db)):
    """A03 微信授权登录：入参 {code}，静默换取 openid 后绑定。"""
    code = body.get("code")
    # 本期对接测试：由前端直接传 openid（正式接入微信 code2session）
    openid = body.get("openid") or (f"test_{code}" if code else "")
    user = AuthService.wechat_login(db, openid)
    at, rt, *_ = create_pair(user)
    return ok({"access_token": at, "refresh_token": rt, "user": UserOut.model_validate(user)})


def create_pair(user):
    from app.core.security import create_access_token, create_refresh_token
    return create_access_token(str(user.id)), create_refresh_token(str(user.id)), None