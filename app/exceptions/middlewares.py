# -*- coding: utf-8 -*-
"""中间件：请求日志（移植自 ai_health 项目）。

用法：register_middlewares(app)
"""
import os
import time

from fastapi import FastAPI, Request

from app.utils.logger import logger


def register_middlewares(app: FastAPI):
    """注册中间件"""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录所有 HTTP 请求"""
        start_time = time.time()

        # 请求日志
        logger.info(f"→ {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"← {request.method} {request.url.path} "
                f"- {response.status_code} - {process_time:.3f}s"
            )
            return response
        except Exception as e:
            logger.error(f"✗ {request.method} {request.url.path} - 异常: {e}")
            raise

    # 只在主进程打印
    if not os.environ.get("UVICORN_RELOADER"):
        logger.info("✅ 中间件注册完成")
