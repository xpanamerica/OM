from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_INVALID_CODE = "TURNSTILE_INVALID"
TURNSTILE_REQUIRED_CODE = "TURNSTILE_REQUIRED"
TURNSTILE_NOT_CONFIGURED_CODE = "TURNSTILE_NOT_CONFIGURED"
TURNSTILE_HOSTNAME_INVALID_CODE = "TURNSTILE_HOSTNAME_INVALID"
TURNSTILE_ACTION_INVALID_CODE = "TURNSTILE_ACTION_INVALID"


def verify_turnstile_token(token: str | None, *, remote_ip: str | None, expected_action: str | None = None) -> None:
    """校验 Cloudflare Turnstile token；失败时抛业务错误阻断请求。"""
    submitted = (token or "").strip()
    if settings.TURNSTILE_BYPASS:
        return
    if not submitted:
        raise AppError("请先完成人机验证。", status_code=400, code=TURNSTILE_REQUIRED_CODE)
    if settings.TURNSTILE_SECRET is None:
        logger.error("Turnstile verification requested but TURNSTILE_SECRET is not configured")
        raise AppError("人机验证暂不可用，请稍后再试。", status_code=503, code=TURNSTILE_NOT_CONFIGURED_CODE)

    data = {
        "secret": settings.TURNSTILE_SECRET.get_secret_value(),
        "response": submitted,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(SITEVERIFY_URL, data=data)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Turnstile siteverify HTTP failure: %s", exc)
        raise AppError("人机验证暂不可用，请稍后再试。", status_code=503, code=TURNSTILE_NOT_CONFIGURED_CODE) from exc
    except ValueError as exc:
        logger.warning("Turnstile siteverify returned invalid JSON")
        raise AppError("人机验证暂不可用，请稍后再试。", status_code=503, code=TURNSTILE_NOT_CONFIGURED_CODE) from exc

    if result.get("success") is not True:
        logger.info("Turnstile verification failed: %s", result.get("error-codes") or [])
        raise AppError("人机验证失败，请重试。", status_code=400, code=TURNSTILE_INVALID_CODE)

    allowed_hostnames = {h.strip().lower() for h in settings.TURNSTILE_ALLOWED_HOSTNAMES if h.strip()}
    hostname = str(result.get("hostname") or "").strip().lower()
    if allowed_hostnames and hostname not in allowed_hostnames:
        logger.warning("Turnstile hostname mismatch: hostname=%s allowed=%s", hostname, sorted(allowed_hostnames))
        raise AppError("人机验证来源不匹配，请刷新后重试。", status_code=400, code=TURNSTILE_HOSTNAME_INVALID_CODE)

    expected = (expected_action or "").strip()
    actual_action = str(result.get("action") or "").strip()
    if expected and actual_action and actual_action != expected:
        logger.warning("Turnstile action mismatch: actual=%s expected=%s", actual_action, expected)
        raise AppError("人机验证场景不匹配，请刷新后重试。", status_code=400, code=TURNSTILE_ACTION_INVALID_CODE)
