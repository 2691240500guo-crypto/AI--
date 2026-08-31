# -*- coding: utf-8 -*-
"""全局异常与中间件包（移植自 ai_health 项目）。

- base_api_exception.py   异常体系（BaseAPIException + 常用子类）
- exception_handlers.py   全局异常处理器（5 类）
- middlewares.py          请求日志中间件
"""
from app.exceptions.base_api_exception import (
    BaseAPIException,
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ValidationException,
    DatabaseException,
    ExternalServiceException,
    RateLimitExceededException,
    AuthenticationException,
    PermissionException,
)
from app.exceptions.exception_handlers import register_exception_handlers
from app.exceptions.middlewares import register_middlewares

__all__ = [
    "BaseAPIException", "BadRequestException", "ConflictException",
    "NotFoundException", "UnauthorizedException", "ForbiddenException",
    "ValidationException", "DatabaseException", "ExternalServiceException",
    "RateLimitExceededException", "AuthenticationException", "PermissionException",
    "register_exception_handlers", "register_middlewares",
]
