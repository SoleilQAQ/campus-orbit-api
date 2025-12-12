from __future__ import annotations

from datetime import datetime, timezone
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _now():
    return datetime.now(timezone.utc).isoformat()


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "path": str(request.url.path),
            "requestId": getattr(request.state, "request_id", None),
            "timestamp": _now(),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "参数校验失败",
            "errors": exc.errors(),
            "path": str(request.url.path),
            "requestId": getattr(request.state, "request_id", None),
            "timestamp": _now(),
        },
    )
