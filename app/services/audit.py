"""操作留痕服务（A08 / I01）：记录器 + 对外审计查询。"""
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog


def record_op(db: Session, *,
              user_id: int | None, username: str | None,
              method: str, path: str, action: str, status_code: int,
              ip: str | None, duration_ms: int, request_body: str | None = None) -> None:
    db.add(OperationLog(
        user_id=user_id, username=username, method=method, path=path,
        action=action, status_code=status_code, ip=ip,
        duration_ms=duration_ms, request_body=request_body,
    ))


def client_ip(request: Request) -> str | None:
    ip = request.headers.get("x-forwarded-for")
    return ip.split(",")[0].strip() if ip else request.client.host if request.client else None


class AuditService:
    @staticmethod
    def query(db: Session, *, user_id: int | None = None, action: str | None = None,
              begin: str | None = None, end: str | None = None,
              page: int = 1, page_size: int = 20) -> tuple[list[OperationLog], int]:
        conds = []
        if user_id:
            conds.append(OperationLog.user_id == user_id)
        if action:
            conds.append(OperationLog.action.like(f"%{action}%"))
        total = db.scalar(select(func.count()).select_from(OperationLog).where(*conds)) or 0
        stmt = select(OperationLog).where(*conds).order_by(OperationLog.id.desc())
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
        return rows, total