from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core import auth_rate_limit
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories import refresh_token_repository, security_event_repository, user_repository

AUTH_FAILED_MESSAGE = "用户名或密码错误"
REFRESH_TOKEN_INVALID_CODE = "REFRESH_TOKEN_INVALID"


@dataclass(frozen=True)
class IssuedRefreshToken:
    row: RefreshToken
    raw_token: str


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def user_agent_hash(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.strip().encode("utf-8", errors="replace")).hexdigest()


def device_label_from_user_agent(user_agent: str | None) -> str | None:
    ua = (user_agent or "").lower()
    if "iphone" in ua:
        return "iPhone"
    if "android" in ua:
        return "Android"
    if "windows" in ua:
        return "Windows"
    if "macintosh" in ua or "mac os" in ua:
        return "macOS"
    if "linux" in ua:
        return "Linux"
    return "Unknown device" if user_agent else None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def refresh_token_ttl_seconds() -> int:
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 3600


def issue_refresh_token(
    db: Session,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> IssuedRefreshToken:
    raw = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=int(settings.REFRESH_TOKEN_EXPIRE_DAYS))
    ua_hash = user_agent_hash(user_agent)
    existing = refresh_token_repository.list_active_for_user(db, user_id=user.id)
    if existing and any(r.user_agent_hash and ua_hash and r.user_agent_hash != ua_hash for r in existing):
        security_event_repository.insert_event_sync(
            event_type="auth.login.new_device",
            user_id=user.id,
            ip_address=ip_address,
            subject_hash=auth_rate_limit.subject_fingerprint(str(user.id)),
            detail="new_user_agent",
            user_agent=user_agent,
            metadata={"active_session_count": len(existing)},
        )
    if existing and ip_address and all(r.ip_address != ip_address for r in existing if r.ip_address):
        security_event_repository.insert_event_sync(
            event_type="auth.login.new_ip",
            user_id=user.id,
            ip_address=ip_address,
            subject_hash=auth_rate_limit.subject_fingerprint(str(user.id)),
            detail="new_ip_address",
            user_agent=user_agent,
            metadata={"active_session_count": len(existing)},
        )
    row = refresh_token_repository.insert_token(
        db,
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
        user_agent_hash=ua_hash,
        device_label=device_label_from_user_agent(user_agent),
    )
    return IssuedRefreshToken(row=row, raw_token=raw)


def _invalid_refresh(*, ip_address: str | None, detail: str, subject_hash: str | None = None) -> None:
    security_event_repository.insert_event_sync(
        event_type="auth.refresh.denied",
        ip_address=ip_address,
        subject_hash=subject_hash,
        detail=detail,
    )
    raise AppError(AUTH_FAILED_MESSAGE, status_code=401, code=REFRESH_TOKEN_INVALID_CODE)


def rotate_refresh_token(
    db: Session,
    *,
    raw_token: str | None,
    ip_address: str | None,
    user_agent: str | None,
    request_id: str | None = None,
) -> tuple[User, IssuedRefreshToken]:
    submitted = (raw_token or "").strip()
    if not submitted:
        _invalid_refresh(ip_address=ip_address, detail="missing")

    token_hash = hash_refresh_token(submitted)
    row = refresh_token_repository.get_by_token_hash(db, token_hash=token_hash)
    if row is None:
        _invalid_refresh(ip_address=ip_address, detail="not_found")

    subject_hash = auth_rate_limit.subject_fingerprint(str(row.user_id))
    now = datetime.now(UTC)
    if row.revoked_at is not None:
        # 旧 refresh token 再次出现通常代表重放或泄露，保守撤销该用户所有会话。
        refresh_token_repository.revoke_all_for_user(db, user_id=row.user_id, revoked_at=now)
        db.commit()
        security_event_repository.insert_event_sync(
            event_type="auth.refresh.reuse_detected",
            user_id=row.user_id,
            ip_address=ip_address,
            subject_hash=subject_hash,
            detail="reuse_detected",
            request_id=request_id,
            user_agent=user_agent,
        )
        _invalid_refresh(ip_address=ip_address, detail="reuse_detected", subject_hash=subject_hash)

    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        refresh_token_repository.revoke_token(db, token_id=row.id, revoked_at=now)
        db.commit()
        _invalid_refresh(ip_address=ip_address, detail="expired", subject_hash=subject_hash)

    user = user_repository.get_by_id(db, row.user_id)
    if user is None or not user.is_active:
        refresh_token_repository.revoke_token(db, token_id=row.id, revoked_at=now)
        db.commit()
        _invalid_refresh(ip_address=ip_address, detail="inactive_user", subject_hash=subject_hash)

    issued = issue_refresh_token(db, user=user, ip_address=ip_address, user_agent=user_agent)
    refresh_token_repository.mark_used(db, token_id=row.id, used_at=now)
    refresh_token_repository.revoke_token(
        db,
        token_id=row.id,
        replaced_by_token_id=issued.row.id,
        revoked_at=now,
    )
    db.commit()
    security_event_repository.insert_event_sync(
        event_type="auth.refresh.succeeded",
        user_id=user.id,
        ip_address=ip_address,
        subject_hash=subject_hash,
        detail=None,
        request_id=request_id,
        user_agent=user_agent,
        metadata={"old_token_id": str(row.id), "new_token_id": str(issued.row.id)},
    )
    return user, issued


def delete_refresh_token(
    db: Session,
    *,
    raw_token: str | None,
    ip_address: str | None,
    request_id: str | None = None,
    user_agent: str | None = None,
) -> bool:
    submitted = (raw_token or "").strip()
    if not submitted:
        return False
    row = refresh_token_repository.get_by_token_hash(db, token_hash=hash_refresh_token(submitted))
    if row is None:
        return False
    deleted = refresh_token_repository.delete_token(db, token_id=row.id) > 0
    db.commit()
    security_event_repository.insert_event_sync(
        event_type="auth.logout",
        user_id=row.user_id,
        ip_address=ip_address,
        subject_hash=auth_rate_limit.subject_fingerprint(str(row.user_id)),
        detail="refresh_token_deleted" if deleted else "refresh_token_missing",
        request_id=request_id,
        user_agent=user_agent,
    )
    return deleted


def revoke_all_for_user(
    db: Session,
    *,
    user_id,
    ip_address: str | None,
    detail: str,
    request_id: str | None = None,
    user_agent: str | None = None,
) -> int:
    n = refresh_token_repository.revoke_all_for_user(db, user_id=user_id)
    security_event_repository.insert_event_sync(
        event_type="auth.refresh.revoked_all",
        user_id=user_id,
        ip_address=ip_address,
        subject_hash=auth_rate_limit.subject_fingerprint(str(user_id)),
        detail=detail,
        request_id=request_id,
        user_agent=user_agent,
        metadata={"revoked_count": n},
    )
    return n


def active_sessions(db: Session, *, user: User, current_raw_token: str | None) -> list[dict[str, object]]:
    current_hash = hash_refresh_token(current_raw_token) if current_raw_token else ""
    sessions = []
    for row in refresh_token_repository.list_active_for_user(db, user_id=user.id):
        sessions.append(
            {
                "id": str(row.id),
                "device_label": row.device_label,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "created_at": row.created_at,
                "last_used_at": row.last_used_at,
                "expires_at": row.expires_at,
                "is_current": bool(current_hash and row.token_hash == current_hash),
            }
        )
    return sessions


def revoke_session(db: Session, *, user: User, token_id, current_raw_token: str | None) -> bool:
    row = refresh_token_repository.get_active_for_user(db, user_id=user.id, token_id=token_id)
    if row is None:
        return False
    refresh_token_repository.revoke_token(db, token_id=row.id)
    db.commit()
    return bool(current_raw_token and row.token_hash == hash_refresh_token(current_raw_token))


def revoke_other_sessions(db: Session, *, user: User, current_raw_token: str | None) -> int:
    current_hash = hash_refresh_token(current_raw_token) if current_raw_token else ""
    count = 0
    for row in refresh_token_repository.list_active_for_user(db, user_id=user.id):
        if current_hash and row.token_hash == current_hash:
            continue
        refresh_token_repository.revoke_token(db, token_id=row.id)
        count += 1
    db.commit()
    return count
