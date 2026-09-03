"""在业务写请求成功后使统计缓存整体换代。"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.redis_client import get_redis_service


_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ANALYTICS_SOURCES = (
    "/api/v1/talent",
    "/api/v1/assessment",
    "/api/v1/training",
    "/api/v1/matching",
    "/api/v1/depts",
)
_AUTH_SOURCES = (
    "/api/v1/users",
    "/api/v1/roles",
    "/api/v1/menus",
)
_MESSAGE_SOURCES = (
    "/api/v1/messages",
    "/api/v1/assessment",
    "/api/v1/training",
    "/api/v1/matching",
)


def _invalidate_auth_caches() -> None:
    service = get_redis_service()
    service.invalidate_namespace("auth")
    service.invalidate_namespace("navigation")


class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if (
            request.method in _WRITE_METHODS
            and response.status_code < 400
            and request.url.path.startswith(_ANALYTICS_SOURCES)
        ):
            await run_in_threadpool(
                get_redis_service().invalidate_namespace,
                "analytics",
            )
        if (
            request.method in _WRITE_METHODS
            and response.status_code < 400
            and request.url.path.startswith(_AUTH_SOURCES)
        ):
            await run_in_threadpool(_invalidate_auth_caches)
        if (
            request.method in _WRITE_METHODS
            and response.status_code < 400
            and request.url.path.startswith(_MESSAGE_SOURCES)
        ):
            await run_in_threadpool(
                get_redis_service().invalidate_namespace,
                "messages",
            )
        return response
