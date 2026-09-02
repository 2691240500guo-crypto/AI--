from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.role import RoleOut


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = ""
    phone: str | None = None
    email: str | None = None
    dept_id: int | None = None
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    nickname: str | None = None
    phone: str | None = None
    email: str | None = None
    dept_id: int | None = None
    role_ids: list[int] | None = None
    status: int | None = None
    password: str | None = None  # 不为空则重置密码


class UserQuery(BaseModel):
    """分页查询条件（接口按 query 参数传入时另写，此处见 routers/user.py）。"""
    page: int = 1
    page_size: int = 20
    keyword: str | None = None
    dept_id: int | None = None
    status: int | None = None


class UserOut(ORMModel):
    id: int
    username: str
    nickname: str
    phone: str | None
    email: str | None
    avatar: str | None
    dept_id: int | None
    status: int
    is_super: int
    last_login_at: datetime | None
    talent_id: int | None = None   # 员工端 miniapp 拿当前 talent 身份（修复 fallback 11 隐患）
    emp_no: str | None = None
    user_type: str = "admin"
    roles: list[RoleOut] = []