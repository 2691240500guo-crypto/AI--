from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = {"from_attributes": True}


class PageBase(BaseModel, Generic[T]):
    items: list[T]
    meta: dict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


# 供循环引用使用的前向声明
from app.schemas.user import UserOut  # noqa: E402

TokenResponse.model_rebuild()