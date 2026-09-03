"""应用入口：装配 FastAPI 应用。

启动：uvicorn app.main:app --reload
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path：
# 支持 `python app/main.py`（脚本模式）与 `uvicorn app.main:app`（模块模式）两种启动方式
_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.exceptions.middlewares import register_middlewares
from app.exceptions.exception_handlers import register_exception_handlers
from app.middleware.audit import AuditMiddleware
from app.middleware.cache_invalidation import CacheInvalidationMiddleware
from app.routers.api import api
import app.models  # noqa: F401  确保 model 注册进 Base.metadata

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

# CORS：允许管理端(5173)与小程序(开发)来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(CacheInvalidationMiddleware)

# 全局异常处理器（业务异常/参数校验/HTTP 异常/兜底 500，统一响应格式）
register_exception_handlers(app)
# 请求日志中间件
register_middlewares(app)


@app.on_event("startup")
def on_startup() -> None:
    # 云端库结构由 Alembic 管理，演示数据由显式脚本管理。默认启动不执行
    # create_all/全量播种，避免多实例启动时锁表或被云端网络波动拖住。
    if settings.AUTO_INIT_DB:
        from app.db.init_db import init_db
        init_db()
    if settings.REDIS_ENABLED:
        from app.core.redis_client import get_redis_service
        if get_redis_service().ping():
            print("Redis connection ready")
        else:
            print("Redis unavailable; optional features will degrade")


@app.on_event("shutdown")
def on_shutdown() -> None:
    from app.core.redis_client import get_redis_service
    get_redis_service().close()


app.include_router(api, prefix=settings.API_PREFIX)


@app.get("/health", tags=["meta"])
def health():
    from app.core.redis_client import get_redis_service
    redis_service = get_redis_service()
    return {
        "status": "ok",
        "redis": {
            "enabled": redis_service.enabled,
            "available": redis_service.available,
            "required": False,
        },
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
