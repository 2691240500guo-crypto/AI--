"""操作留痕服务（A08 / I01）：记录器 + 对外审计查询。"""
from datetime import datetime  # 时间类型与解析

from fastapi import Request  # 请求对象
from sqlalchemy import func, select  # 聚合函数与查询构造器
from sqlalchemy.orm import Session  # 数据库会话类型

from app.models.operation_log import LoginLog, OperationLog  # 登录日志与操作日志模型
from app.utils.response import BusinessError  # 业务异常


def record_op(db: Session, *,
              user_id: int | None, username: str | None,
              method: str, path: str, action: str, status_code: int,
              ip: str | None, duration_ms: int, request_body: str | None = None) -> None:
    """记录一条操作日志。"""
    db.add(OperationLog(  # 新增操作日志对象
        user_id=user_id, username=username, method=method, path=path,  # 操作人与请求信息
        action=action, status_code=status_code, ip=ip,  # 动作与状态信息
        duration_ms=duration_ms, request_body=request_body,  # 耗时与请求体
    ))


def client_ip(request: Request) -> str | None:
    """从请求头或客户端地址提取 IP。"""
    ip = request.headers.get("x-forwarded-for")  # 优先取代理转发头
    return ip.split(",")[0].strip() if ip else request.client.host if request.client else None  # 取第一个 IP 或直连地址


def _parse_datetime(value: str | None) -> datetime | None:
    """解析筛选时间字符串，格式错误抛业务异常。"""
    if not value:  # 空值直接返回 None
        return None
    try:  # 尝试解析 ISO 时间
        return datetime.fromisoformat(value.replace("Z", "+00:00"))  # 兼容 Z 结尾时间
    except ValueError:  # 解析失败
        raise BusinessError(400, "时间格式错误")  # 抛出统一业务异常


def _op_conds(*, user_id: int | None = None, username: str | None = None, action: str | None = None,
              begin: str | None = None, end: str | None = None) -> list:
    """构造操作日志筛选条件。"""
    conds = []  # 筛选条件列表
    if user_id:  # 按用户 id 精确过滤
        conds.append(OperationLog.user_id == user_id)  # 追加用户条件
    if username:  # 按用户名模糊过滤
        conds.append(OperationLog.username.like(f"%{username}%"))  # 追加用户名条件
    if action:  # 按动作模糊过滤
        conds.append(OperationLog.action.like(f"%{action}%"))  # 追加动作条件
    begin_dt = _parse_datetime(begin)  # 解析开始时间
    end_dt = _parse_datetime(end)  # 解析结束时间
    if begin_dt:  # 开始时间非空
        conds.append(OperationLog.created_at >= begin_dt)  # 追加时间下限
    if end_dt:  # 结束时间非空
        conds.append(OperationLog.created_at <= end_dt)  # 追加时间上限
    return conds  # 返回条件列表


def _login_conds(*, username: str | None = None, begin: str | None = None, end: str | None = None) -> list:
    """构造登录日志筛选条件。"""
    conds = []  # 筛选条件列表
    if username:  # 按用户名模糊过滤
        conds.append(LoginLog.username.like(f"%{username}%"))  # 追加用户名条件
    begin_dt = _parse_datetime(begin)  # 解析开始时间
    end_dt = _parse_datetime(end)  # 解析结束时间
    if begin_dt:  # 开始时间非空
        conds.append(LoginLog.created_at >= begin_dt)  # 追加时间下限
    if end_dt:  # 结束时间非空
        conds.append(LoginLog.created_at <= end_dt)  # 追加时间上限
    return conds  # 返回条件列表


class AuditService:
    """审计查询业务服务。"""

    @staticmethod
    def query(db: Session, *, user_id: int | None = None, username: str | None = None,
              action: str | None = None, begin: str | None = None, end: str | None = None,
              page: int = 1, page_size: int = 20) -> tuple[list[OperationLog], int]:
        """查询操作日志，返回行列表与总数。"""
        conds = _op_conds(user_id=user_id, username=username, action=action, begin=begin, end=end)  # 构造筛选条件
        total = db.scalar(select(func.count()).select_from(OperationLog).where(*conds)) or 0  # 统计总数
        stmt = select(OperationLog).where(*conds).order_by(OperationLog.id.desc())  # 构造倒序查询
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())  # 分页取行
        return rows, total  # 返回行列表与总数

    @staticmethod
    def query_export(db: Session, *, user_id: int | None = None, username: str | None = None,
                     action: str | None = None, begin: str | None = None, end: str | None = None,
                     limit: int = 5000) -> list[OperationLog]:
        """导出操作日志，与查询共用同一筛选条件。"""
        conds = _op_conds(user_id=user_id, username=username, action=action, begin=begin, end=end)  # 构造筛选条件
        stmt = select(OperationLog).where(*conds).order_by(OperationLog.id.desc()).limit(limit)  # 倒序限量查询
        return list(db.scalars(stmt).all())  # 返回全部行

    @staticmethod
    def query_login(db: Session, *, username: str | None = None, begin: str | None = None,
                    end: str | None = None, page: int = 1, page_size: int = 20) -> tuple[list[LoginLog], int]:
        """查询登录日志，返回行列表与总数。"""
        conds = _login_conds(username=username, begin=begin, end=end)  # 构造筛选条件
        total = db.scalar(select(func.count()).select_from(LoginLog).where(*conds)) or 0  # 统计总数
        stmt = select(LoginLog).where(*conds).order_by(LoginLog.id.desc())  # 构造倒序查询
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())  # 分页取行
        return rows, total  # 返回行列表与总数

    @staticmethod
    def query_login_export(db: Session, *, username: str | None = None, begin: str | None = None,
                           end: str | None = None, limit: int = 5000) -> list[LoginLog]:
        """导出登录日志，与查询共用同一筛选条件。"""
        conds = _login_conds(username=username, begin=begin, end=end)  # 构造筛选条件
        stmt = select(LoginLog).where(*conds).order_by(LoginLog.id.desc()).limit(limit)  # 倒序限量查询
        return list(db.scalars(stmt).all())  # 返回全部行
