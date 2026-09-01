"""统一响应与业务异常。"""
from typing import Any

from fastapi.responses import JSONResponse


class BusinessError(Exception):
    """业务异常：携带 code 与 message，由异常处理器转成统一响应。"""

    def __init__(self, code: int = 400, message: str = "业务错误"):
        self.code = code
        self.message = message
        super().__init__(message)


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int = 500, message: str = "error") -> dict:
    return {"code": code, "message": message, "data": None}


def business_error_handler(_: Any, exc: BusinessError) -> JSONResponse:
    return JSONResponse(status_code=200, content=fail(exc.code, exc.message))