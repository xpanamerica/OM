from __future__ import annotations

import hmac
import secrets

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError

CSRF_INVALID_CODE = "CSRF_INVALID"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_request(request: Request) -> None:
    cookie_token = (request.cookies.get(settings.CSRF_COOKIE_NAME) or "").strip()
    header_token = (request.headers.get(settings.CSRF_HEADER_NAME) or "").strip()
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise AppError("用户名或密码错误", status_code=401, code=CSRF_INVALID_CODE)
