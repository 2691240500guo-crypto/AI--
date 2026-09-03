"""操作留痕中间件（A08 / I01）。做增删改查时自动记录，业务零侵入。

采集 → 关联当前用户 → 写入 sys_operation_log：
    - 只对写操作（POST/PUT/DELETE）落库，GET 等查询不记（避免噪音）
    - 从 Authorization 头解析 token 拿 user_id/username（未登录则留空）
    - request_body 做密码脱敏后再入库
    - 写库独立会话、失败静默，绝不影响主请求
"""
import asyncio
import json
import time

from fastapi.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.services.audit import record_op

# 只对写操作留痕
_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
_BACKGROUND_TASKS: set[asyncio.Task] = set()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        # 只对业务接口留痕，跳过文档/静态
        if request.url.path.startswith("/api"):
            body = None
            try:
                raw = await request.body()
                body = raw.decode("utf-8", "ignore")[:2000] if raw else None
            except Exception:
                pass
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            # 写操作才落库（GET 等查询不记录）
            if request.method in _WRITE_METHODS:
                try:
                    user_id, username = _resolve_user(request)
                    # 审计为尽力写入，不能让云数据库延迟阻塞业务响应。
                    task = asyncio.create_task(
                        _persist_safely(
                            user_id=user_id, username=username,
                            method=request.method, path=request.url.path,
                            status_code=response.status_code, ip=_ip(request),
                            duration_ms=duration_ms, request_body=_mask(body),
                        )
                    )
                    _BACKGROUND_TASKS.add(task)
                    task.add_done_callback(_BACKGROUND_TASKS.discard)
                except Exception:
                    pass  # 审计失败静默，不影响主请求
            request.state.audit = {
                "method": request.method, "path": request.url.path,
                "status_code": response.status_code, "duration_ms": duration_ms,
                "body": body, "ip": _ip(request),
            }
            return response
        return await call_next(request)


def _resolve_user(request: Request) -> tuple[int | None, str | None]:
    """从 Authorization: Bearer <token> 解析当前用户 (user_id, username)。未登录返回 (None, None)。"""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None, None
    payload = decode_token(auth[7:])
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        return None, None
    user_id = int(payload["sub"])
    # 注销接口必须在数据库暂时不可用时仍能撤销 Redis 中的令牌。
    # user_id 已包含在已签名 JWT 中，审计日志允许 username 为空。
    if request.url.path.endswith("/auth/logout"):
        return user_id, None
    username = None
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user:
            username = user.username
    finally:
        db.close()
    return user_id, username


def _mask(body: str | None) -> str | None:
    """敏感字段（password/token）脱敏后再入库。"""
    if not body:
        return body
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            for key in list(data.keys()):
                if "password" in key.lower() or "token" in key.lower():
                    data[key] = "***"
            return json.dumps(data, ensure_ascii=False)[:2000]
    except Exception:
        pass
    return body[:2000]


def _persist(*, user_id: int | None, username: str | None, method: str, path: str,
             status_code: int, ip: str | None, duration_ms: int, request_body: str | None) -> None:
    """独立会话写审计日志。"""
    db = SessionLocal()
    try:
        record_op(db, user_id=user_id, username=username, method=method, path=path,
                  action=f"{method} {path}", status_code=status_code, ip=ip,
                  duration_ms=duration_ms, request_body=request_body)
        db.commit()
    finally:
        db.close()


async def _persist_safely(**kwargs) -> None:
    """在线程池后台写审计，云数据库异常或延迟不影响主请求。"""
    try:
        await run_in_threadpool(_persist, **kwargs)
    except Exception:
        pass


def _ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
