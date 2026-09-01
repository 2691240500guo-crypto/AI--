from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RoleCreate(BaseModel):
    code: str = Field(min_length=2)
    name: str
    remark: str | None = None
    menu_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    remark: str | None = None
    menu_ids: list[int] | None = None
    status: int | None = None


class RoleOut(ORMModel):
    id: int
    code: str
    name: str
    remark: str | None
    status: int
    created_at: datetime | None


class MenuCreate(BaseModel):
    parent_id: int = 0
    title: str
    icon: str | None = None
    path: str | None = None
    component: str | None = None
    perm: str | None = None
    type: int = 2
    sort: int = 0


class MenuOut(ORMModel):
    id: int
    parent_id: int
    title: str
    icon: str | None
    path: str | None
    component: str | None
    perm: str | None
    type: int
    sort: int
    status: int