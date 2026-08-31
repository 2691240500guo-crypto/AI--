"""认证服务：登录/登出/token 续期/微信登录(A01-A03)。"""
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import (create_access_token, create_refresh_token,
                               hash_password, verify_password)
from app.dao.user import UserDAO
from app.models.operation_log import LoginLog
from app.models.user import User, UserRole
from app.utils.response import BusinessError


class AuthService:
    @staticmethod
    def authenticate(db: Session, username: str, password: str, ip: str | None = None) -> User:
        user = UserDAO.get_by(db, username=username.strip())
        if not user or not verify_password(password, user.password):
            AuthService._login_log(db, username, 0, "账号或密码错误", ip)
            raise BusinessError(400, "账号或密码错误")
        if user.status != 1:
            AuthService._login_log(db, username, 0, "账号被禁用", ip)
            raise BusinessError(403, "账号已被禁用")
        user.last_login_at = datetime.now()
        db.flush()
        AuthService._login_log(db, username, 1, "登录成功", ip)
        return user

    @staticmethod
    def login(db: Session, username: str, password: str, ip: str | None = None) -> tuple[User, str, str]:
        user = AuthService.authenticate(db, username, password, ip)
        at = create_access_token(str(user.id))
        rt = create_refresh_token(str(user.id))
        return user, at, rt

    @staticmethod
    def refresh(db: Session, refresh_token: str) -> tuple[str, str]:
        from app.core.security import decode_token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh" or not payload.get("sub"):
            raise BusinessError(401, "续期凭证无效")
        user = UserDAO.get(db, int(payload["sub"]))
        if not user or user.status != 1:
            raise BusinessError(401, "用户不存在或已禁用")
        return create_access_token(str(user.id)), create_refresh_token(str(user.id))

    @staticmethod
    def wechat_login(db: Session, openid: str) -> User:
        user = UserDAO.get_by(db, openid=openid)
        if not user:
            raise BusinessError(400, "未找到该微信用户，请联系管理员")
        if user.status != 1:
            raise BusinessError(403, "账号已被禁用")
        return user

    @staticmethod
    def _login_log(db: Session, username: str, success: int, message: str, ip: str | None) -> None:
        db.add(LoginLog(username=username, success=success, message=message, ip=ip))


class UserService:
    @staticmethod
    def create(db: Session, data) -> User:
        if UserDAO.get_by(db, username=data.username):
            raise BusinessError(400, "用户名已存在")
        user = UserDAO.create(
            db, username=data.username, password=hash_password(data.password),
            nickname=data.nickname or data.username, phone=data.phone, email=data.email,
            dept_id=data.dept_id,
        )
        if data.role_ids:
            UserDAO.set_roles(db, user.id, data.role_ids)
        return user

    @staticmethod
    def update(db: Session, user: User, data) -> User:
        fields = {}
        if data.nickname is not None:
            fields["nickname"] = data.nickname
        for f in ("phone", "email", "dept_id", "status"):
            v = getattr(data, f)
            if v is not None:
                fields[f] = v
        if data.password:
            fields["password"] = hash_password(data.password)
        if data.role_ids is not None:
            UserDAO.set_roles(db, user.id, data.role_ids)
        return UserDAO.update(db, user, **fields)

    @staticmethod
    def delete(db: Session, user_id: int) -> None:
        from app.models.user import UserRole
        db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        user = UserDAO.get(db, user_id)
        if user:
            UserDAO.delete(db, user)