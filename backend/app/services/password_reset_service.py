"""忘记密码：签发一次性令牌、可选邮件/日志投递；``POST /auth/reset-password`` 消费令牌。"""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core import auth_rate_limit
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import get_password_hash
from app.repositories import password_reset_repository, security_event_repository, user_repository
from app.services import refresh_token_service

_log = logging.getLogger("app.password_reset")


def _hash_raw_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def _generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def _build_reset_url(plain_token: str) -> str:
    tpl = (settings.AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE or "").strip()
    if "{token}" in tpl:
        enc = quote(plain_token, safe="")
        return tpl.replace("{token}", enc)
    return f"(configure AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE with {{token}}) token={plain_token}"


def _deliver(*, to_email: str, reset_url: str, plain_token: str) -> None:
    backend = (settings.AUTH_PASSWORD_RESET_EMAIL_BACKEND or "noop").strip().lower()
    if backend == "noop":
        return
    subject = "重置您的账户密码"
    body = (
        "您好，\n\n"
        "我们收到了重置密码的请求。请在有效期内点击下方链接（或复制到浏览器）完成重置：\n\n"
        f"{reset_url}\n\n"
        "若您未发起该请求，请忽略本邮件。\n"
    )
    if backend == "log":
        _log.info(
            "password_reset_delivery_log to=%s reset_url=%s",
            to_email,
            reset_url,
            extra={"plain_token": plain_token},
        )
        return
    if backend == "smtp":
        _send_smtp(to_email=to_email, subject=subject, body=body)
        return
    _log.warning("unknown AUTH_PASSWORD_RESET_EMAIL_BACKEND=%s", backend)


def _send_smtp(*, to_email: str, subject: str, body: str) -> None:
    host = (settings.SMTP_HOST or "").strip()
    from_addr = (settings.AUTH_PASSWORD_RESET_EMAIL_FROM or "").strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, int(settings.SMTP_PORT), timeout=30) as server:
        if settings.SMTP_USE_TLS:
            server.starttls(context=context)
        user = (settings.SMTP_USER or "").strip()
        if user:
            pw = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD is not None else ""
            server.login(user, pw)
        server.send_message(msg)


def request_password_reset(db: Session, *, email_normalized: str, client_ip: str | None) -> None:
    """对已存在且启用的用户签发令牌并投递；**邮箱不存在或未启用时不写库**（防枚举）。"""
    user = user_repository.get_by_email(db, email_normalized)
    if user is None or not user.is_active:
        return
    ttl = int(settings.AUTH_PASSWORD_RESET_TOKEN_TTL_SECONDS)
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
    raw = _generate_raw_token()
    th = _hash_raw_token(raw)
    password_reset_repository.delete_unused_for_user(db, user_id=user.id)
    password_reset_repository.insert_token(db, user_id=user.id, token_hash=th, expires_at=expires_at)
    db.commit()
    reset_url = _build_reset_url(raw)
    try:
        _deliver(to_email=user.email, reset_url=reset_url, plain_token=raw)
    except Exception:
        _log.exception("password_reset_deliver_failed user_id=%s", user.id)


def complete_password_reset(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
    client_ip: str | None,
) -> None:
    """校验令牌并更新口令；失败时统一 ``PASSWORD_RESET_INVALID`` 文案。"""
    th = _hash_raw_token(raw_token)
    row = password_reset_repository.get_active_by_token_hash(db, token_hash=th)
    if row is None:
        raise AppError("重置链接无效或已过期。", status_code=400, code="PASSWORD_RESET_INVALID")
    user = user_repository.get_by_id(db, row.user_id)
    if user is None or not user.is_active:
        raise AppError("重置链接无效或已过期。", status_code=400, code="PASSWORD_RESET_INVALID")
    hp = get_password_hash(new_password)
    user_repository.update_user_hashed_password(db, user_id=user.id, hashed_password=hp)
    password_reset_repository.mark_used(db, token_id=row.id)
    refresh_token_service.revoke_all_for_user(
        db,
        user_id=user.id,
        ip_address=client_ip,
        detail="password_reset",
    )
    db.commit()
    auth_rate_limit.clear_login_failures(user.email)
    auth_rate_limit.clear_login_failures(user.username)
    try:
        security_event_repository.insert_event_sync(
            event_type="password_reset.completed",
            ip_address=client_ip,
            subject_hash=auth_rate_limit.subject_fingerprint(user.email),
            detail=None,
        )
    except Exception:
        _log.exception("password_reset_security_event_failed user_id=%s", user.id)
