# -*- coding: utf-8 -*-
"""全局异常处理器（移植自 ai_health 项目，适配本项目 {code, message, data} 约定）。

覆盖五类：
    1. BusinessError           —— 本项目原有业务异常（HTTP 200 + code 区分）
    2. BaseAPIException        —— 自定义异常体系（HTTP 状态码真实）
    3. RequestValidationError  —— 请求参数校验失败（422）
    4. StarletteHTTPException  —— 404/401/403 等 HTTP 异常（收敛为统一格式）
    5. Exception               —— 兜底 500
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base_api_exception import BaseAPIException
from app.utils.logger import logger
from app.utils.response import BusinessError


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""

    # ===== 1. 本项目原有业务异常 BusinessError =====
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        logger.error(f"业务异常: {exc.__class__.__name__} - code: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=200,  # 保持本项目约定：业务错误用 HTTP 200 + code 区分
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
                "path": request.url.path,
                "type": exc.__class__.__name__
            }
        )

    # ===== 2. 自定义异常体系 BaseAPIException =====
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        logger.error(
            f"业务异常: {exc.__class__.__name__} - "
            f"状态码: {exc.status_code} - "
            f"详情: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "data": None,
                "path": request.url.path,
                "type": exc.__class__.__name__
            }
        )

    # ===== 3. 请求参数验证异常 =====
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        logger.error(f"验证异常: {errors}")
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "Validation error",
                "data": {"errors": errors},
                "path": request.url.path
            }
        )

    # ===== 4. HTTP 异常（404/401/403 等，收敛为统一格式） =====
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.error(f"HTTP异常: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": str(exc.detail),
                "data": None,
                "path": request.url.path
            }
        )

    # ===== 5. 兜底：处理所有未捕获的异常 =====
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # 如果是自定义异常，不重复记录（已被上层处理器记录）
        if isinstance(exc, (BaseAPIException, BusinessError)):
            return JSONResponse(
                status_code=getattr(exc, "status_code", 500),
                content={
                    "code": getattr(exc, "status_code", 500),
                    "message": getattr(exc, "detail", getattr(exc, "message", "error")),
                    "data": None,
                    "path": request.url.path,
                    "type": exc.__class__.__name__
                }
            )

        # 只记录真正的未知异常
        logger.error(f"系统异常: {type(exc).__name__}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "data": None,
                "path": request.url.path
            }
        )

    logger.info("✅ 全局异常处理器注册完成")
