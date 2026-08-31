from pydantic import BaseModel

from app.schemas.common import ORMModel


class DeptCreate(BaseModel):
    parent_id: int = 0
    name: str
    leader: str | None = None
    sort: int = 0


class DeptOut(ORMModel):
    id: int
    parent_id: int
    name: str
    leader: str | None
    sort: int
    status: int


class DictTypeCreate(BaseModel):
    code: str
    name: str
    remark: str | None = None


class DictItemCreate(BaseModel):
    type_code: str
    label: str
    value: str
    sort: int = 0
    status: int = 1


class DictItemOut(ORMModel):
    id: int
    type_code: str
    label: str
    value: str
    sort: int
    status: int