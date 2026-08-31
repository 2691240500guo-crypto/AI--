from datetime import datetime

from app.schemas.common import ORMModel


class OperationLogOut(ORMModel):
    id: int
    user_id: int | None
    username: str | None
    method: str
    path: str
    action: str
    status_code: int
    ip: str | None
    duration_ms: int
    request_body: str | None
    created_at: datetime


class LoginLogOut(ORMModel):
    id: int
    username: str
    success: int
    message: str | None
    ip: str | None
    created_at: datetime