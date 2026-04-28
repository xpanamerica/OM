"""HTTP 状态码 → 统一 ``code`` 字段。"""

from __future__ import annotations

from app.core import http_error_codes as c


def error_code_for_http_status(status_code: int) -> str:
    if status_code == 400:
        return c.HTTP_BAD_REQUEST
    if status_code == 401:
        return c.HTTP_UNAUTHORIZED
    if status_code == 403:
        return c.HTTP_FORBIDDEN
    if status_code == 404:
        return c.HTTP_NOT_FOUND
    if status_code == 409:
        return c.HTTP_CONFLICT
    if status_code == 422:
        return c.HTTP_VALIDATION_ERROR
    if status_code >= 500:
        return c.HTTP_INTERNAL_SERVER_ERROR
    return "http_error"
