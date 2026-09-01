"""审计/日志路由（A08/A09/I01/I02）：对外接口层，筛选逻辑交给 service。"""
import csv  # CSV 导出
import io  # 内存文本流

from fastapi import APIRouter, Depends, Query  # 路由与依赖
from fastapi.responses import StreamingResponse  # 流式文件响应
from sqlalchemy.orm import Session  # 数据库会话类型

from app.core.deps import require_permission  # 权限依赖
from app.db.session import get_db  # 数据库会话依赖
from app.schemas.log import LoginLogOut, OperationLogOut  # 日志输出 DTO
from app.services.audit import AuditService  # 审计业务服务
from app.utils.pagination import paged_result  # 分页响应工具
from app.utils.response import ok  # 统一成功响应

router = APIRouter(dependencies=[Depends(require_permission("system:audit"))])  # 审计接口统一要求 system:audit 权限

# 导出时一次最多取的行数
EXPORT_LIMIT = 5000


@router.get("/operations", summary="查询操作日志")
def query_ops(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
              action: str | None = None, user_id: int | None = None,
              username: str | None = None, begin: str | None = None, end: str | None = None,
              db: Session = Depends(get_db)):
    """按时间/用户/动作筛选操作日志，支持分页。"""
    rows, total = AuditService.query(db, user_id=user_id, username=username, action=action,  # 调用业务层查询
                                     begin=begin, end=end, page=page, page_size=page_size)  # 传入筛选与分页参数
    return ok(paged_result([OperationLogOut.model_validate(r) for r in rows], page, page_size, total))  # 返回分页结果


@router.get("/operations/export", summary="导出操作日志 CSV")
def export_ops(action: str | None = None, user_id: int | None = None,
               username: str | None = None, begin: str | None = None, end: str | None = None,
               db: Session = Depends(get_db)):
    """按查询同款条件导出操作日志 CSV。"""
    rows = AuditService.query_export(db, user_id=user_id, username=username, action=action,  # 调用导出查询
                                     begin=begin, end=end, limit=EXPORT_LIMIT)  # 限制导出行数
    buf = io.StringIO()  # 创建内存文本流
    writer = csv.writer(buf)  # 创建 CSV 写入器
    writer.writerow(["ID", "用户ID", "用户名", "方法", "路径", "动作", "状态码", "IP", "耗时ms", "请求内容", "时间"])  # 写表头
    for r in rows:  # 逐行写数据
        writer.writerow([  # 按列输出
            r.id, r.user_id, r.username or "", r.method, r.path,  # 基础字段
            r.action, r.status_code, r.ip or "", r.duration_ms,  # 动作状态与耗时
            (r.request_body or "").replace("\n", " "), r.created_at.strftime("%Y-%m-%d %H:%M:%S"),  # 请求内容与时间
        ])
    data = "\ufeff" + buf.getvalue()  # 加 BOM 防止 Excel 中文乱码
    return StreamingResponse(  # 返回文件流
        iter([data.encode("utf-8")]),  # 编码后输出
        media_type="text/csv",  # CSV 类型
        headers={"Content-Disposition": "attachment; filename=operation_logs.csv"},  # 下载文件名
    )


@router.get("/logins", summary="查询登录日志")
def login_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
               username: str | None = None, begin: str | None = None, end: str | None = None,
               db: Session = Depends(get_db)):
    """按时间/用户名筛选登录日志，支持分页。"""
    rows, total = AuditService.query_login(db, username=username, begin=begin, end=end,  # 调用业务层查询
                                           page=page, page_size=page_size)  # 传入分页参数
    return ok(paged_result([LoginLogOut.model_validate(r) for r in rows], page, page_size, total))  # 返回分页结果


@router.get("/logins/export", summary="导出登录日志 CSV")
def export_login_logs(username: str | None = None, begin: str | None = None, end: str | None = None,
                      db: Session = Depends(get_db)):
    """按查询同款条件导出登录日志 CSV。"""
    rows = AuditService.query_login_export(db, username=username, begin=begin, end=end, limit=EXPORT_LIMIT)  # 调用导出查询
    buf = io.StringIO()  # 创建内存文本流
    writer = csv.writer(buf)  # 创建 CSV 写入器
    writer.writerow(["ID", "用户名", "成功", "说明", "IP", "时间"])  # 写表头
    for r in rows:  # 逐行写数据
        writer.writerow([  # 按列输出
            r.id, r.username, "成功" if r.success == 1 else "失败",  # 登录结果
            r.message or "", r.ip or "", r.created_at.strftime("%Y-%m-%d %H:%M:%S"),  # 说明与时间
        ])
    data = "\ufeff" + buf.getvalue()  # 加 BOM 防止 Excel 中文乱码
    return StreamingResponse(  # 返回文件流
        iter([data.encode("utf-8")]),  # 编码后输出
        media_type="text/csv",  # CSV 类型
        headers={"Content-Disposition": "attachment; filename=login_logs.csv"},  # 下载文件名
    )
