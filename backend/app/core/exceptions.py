import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.http_error_codes import HTTP_INTERNAL_SERVER_ERROR, HTTP_VALIDATION_ERROR
from app.core.http_error_utils import error_code_for_http_status
from app.core.video_codes import VIDEO_CONFLICT_OPTIMISTIC

logger = logging.getLogger("app.error")


class AuthRateLimitExceeded(Exception):
    """认证端点限流；由全局处理器返回统一 JSON 体。"""

    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__("rate_limited")


class AppError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = headers or {}
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthRateLimitExceeded)
    async def auth_rate_limit_handler(_: Request, exc: AuthRateLimitExceeded):
        headers: dict[str, str] = {}
        if exc.retry_after is not None and exc.retry_after >= 1:
            headers["Retry-After"] = str(int(exc.retry_after))
        return JSONResponse(
            status_code=429,
            content={"success": False, "message": "请求过于频繁，请稍后再试。"},
            headers=headers or None,
        )

    @app.exception_handler(StaleDataError)
    async def stale_data_handler(_: Request, exc: StaleDataError):
        _ = exc
        return JSONResponse(
            status_code=409,
            content={
                "detail": "资源已被他人更新，请刷新后重试",
                "code": VIDEO_CONFLICT_OPTIMISTIC,
            },
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        body: dict[str, Any] = {"detail": exc.message}
        if exc.code is not None:
            body["code"] = exc.code
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(exc.errors()),
                "code": HTTP_VALIDATION_ERROR,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, str | bytes):
            payload_detail: str | list[Any] = (
                detail.decode("utf-8", errors="replace") if isinstance(detail, bytes) else detail
            )
        else:
            payload_detail = detail
        code = error_code_for_http_status(exc.status_code)
        body: dict[str, Any] = {"detail": payload_detail, "code": code}
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = request.headers.get("x-request-id") or request.headers.get("X-Request-ID") or ""
        logger.exception(
            "unhandled_exception request_id=%s path=%s method=%s",
            rid,
            request.url.path,
            request.method,
        )
        detail_msg = "服务器内部错误"
        if settings.EXPOSE_INTERNAL_ERROR_DETAILS:
            env = settings.ENVIRONMENT.strip().lower()
            production_like = env in ("production", "prod", "staging")
            if not production_like:
                detail_msg = f"{type(exc).__name__}: {exc}"
        return JSONResponse(
            status_code=500,
            content={"detail": detail_msg, "code": HTTP_INTERNAL_SERVER_ERROR},
        )
