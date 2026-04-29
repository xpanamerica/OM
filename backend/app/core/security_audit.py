"""认证相关安全审计日志（禁止记录口令、令牌原文）。"""

from __future__ import annotations

import logging

logger = logging.getLogger("app.auth.security")


def log_login_rate_limited(client_ip: str) -> None:
    logger.warning("event=login_rate_limited client_ip=%s", client_ip)


def log_login_denied(client_ip: str) -> None:
    logger.info("event=login_denied client_ip=%s", client_ip)


def log_register_conflict(client_ip: str) -> None:
    logger.info("event=register_conflict client_ip=%s", client_ip)


def log_register_rate_limited(client_ip: str) -> None:
    logger.warning("event=register_rate_limited client_ip=%s", client_ip)
