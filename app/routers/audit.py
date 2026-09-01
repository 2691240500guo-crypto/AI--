"""审计/日志路由（A08/A09/I01/I02）。"""
import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.operation_log import LoginLog, OperationLog
from app.schemas.log import LoginLogOut, OperationLogOut
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:audit"))])

# 导出时一次最多取的行数
EXPORT_LIMIT = 5000


@router.get("/logs")
def query_ops(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
              action: str | None = None, user_id: int | None = None,
              db: Session = Depends(get_db)):
    conds = []
    if action:
        conds.append(OperationLog.action.like(f"%{action}%"))
    if user_id:
        conds.append(OperationLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(OperationLog).where(*conds)) or 0
    stmt = select(OperationLog).where(*conds).order_by(OperationLog.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return ok(paged_result([OperationLogOut.model_validate(r) for r in rows], page, page_size, total))


@router.get("/logs/export")
def export_ops(action: str | None = None, user_id: int | None = None,
               db: Session = Depends(get_db)):
    """操作日志导出 CSV（I02）。"""
    conds = []
    if action:
        conds.append(OperationLog.action.like(f"%{action}%"))
    if user_id:
        conds.append(OperationLog.user_id == user_id)
    stmt = select(OperationLog).where(*conds).order_by(OperationLog.id.desc()).limit(EXPORT_LIMIT)
    rows = list(db.scalars(stmt).all())

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "用户ID", "用户名", "方法", "路径", "动作", "状态码", "IP", "耗时ms", "请求内容", "时间"])
    for r in rows:
        writer.writerow([
            r.id, r.user_id, r.username or "", r.method, r.path,
            r.action, r.status_code, r.ip or "", r.duration_ms,
            (r.request_body or "").replace("\n", " "), r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    # 加 BOM 便于 Excel 直接打开中文不乱码
    data = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        iter([data.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=operation_logs.csv"},
    )


@router.get("/login-logs")
def login_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
               username: str | None = None, db: Session = Depends(get_db)):
    conds = []
    if username:
        conds.append(LoginLog.username.like(f"%{username}%"))
    total = db.scalar(select(func.count()).select_from(LoginLog).where(*conds)) or 0
    stmt = select(LoginLog).where(*conds).order_by(LoginLog.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return ok(paged_result([LoginLogOut.model_validate(r) for r in rows], page, page_size, total))


@router.get("/login-logs/export")
def export_login_logs(username: str | None = None, db: Session = Depends(get_db)):
    """登录日志导出 CSV（I02）。"""
    conds = []
    if username:
        conds.append(LoginLog.username.like(f"%{username}%"))
    stmt = select(LoginLog).where(*conds).order_by(LoginLog.id.desc()).limit(EXPORT_LIMIT)
    rows = list(db.scalars(stmt).all())

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "用户名", "成功", "说明", "IP", "时间"])
    for r in rows:
        writer.writerow([
            r.id, r.username, "成功" if r.success == 1 else "失败",
            r.message or "", r.ip or "", r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    data = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        iter([data.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=login_logs.csv"},
    )