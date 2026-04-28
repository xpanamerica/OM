"""与业务无关的 HTTP 层加固（生产类环境启用）。"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.request_context import request_id_cv

_access_logger = logging.getLogger("app.http.access")

# 限制高危浏览器能力，降低 XSS 后滥用传感器/支付等面的风险（与 JSON API 兼容）
_PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """请求摘要日志：方法、路径、状态码、耗时、``X-Request-ID``；不记录 Authorization 与请求体（避免口令/token）。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _access_logger.exception(
                "request_error method=%s path=%s duration_ms=%.2f",
                request.method,
                path,
                elapsed_ms,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        rid = response.headers.get("X-Request-ID") or response.headers.get("x-request-id") or ""
        _access_logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
            rid,
        )
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """透传或生成 ``X-Request-ID``，并写入 ``request_id_cv`` 供审计/追踪关联。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        raw = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        rid = (str(raw).strip() if raw else "") or str(uuid.uuid4())
        rid = rid[:128]
        token = request_id_cv.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_cv.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头：全局层（含 OpenAPI 开发态）+ 严格层（关闭文档/生产面）。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # 全局：MIME 嗅探与 Referrer 对 JSON/HTML 均低风险，开发态开文档时也保留
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.expose_openapi_docs:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
            if settings.SECURITY_HSTS_MAX_AGE > 0:
                response.headers["Strict-Transport-Security"] = f"max-age={settings.SECURITY_HSTS_MAX_AGE}"
        return response
