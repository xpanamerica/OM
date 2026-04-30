from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user_auth_state import UserAuthState


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_or_create_for_update(db: Session, *, user_id: uuid.UUID) -> UserAuthState:
    stmt = select(UserAuthState).where(UserAuthState.user_id == user_id).with_for_update()
    row = db.execute(stmt).scalar_one_or_none()
    if row is not None:
        return row
    row = UserAuthState(user_id=user_id)
    db.add(row)
    db.flush()
    return row


def locked_until_if_active(db: Session, *, user_id: uuid.UUID, now: datetime | None = None) -> datetime | None:
    row = db.get(UserAuthState, user_id)
    if row is None:
        return None
    locked_until = _as_utc(row.locked_until)
    current = now or datetime.now(UTC)
    if locked_until is not None and locked_until > current:
        return locked_until
    return None


def record_failure(db: Session, *, user_id: uuid.UUID, now: datetime | None = None) -> UserAuthState:
    current = now or datetime.now(UTC)
    row = get_or_create_for_update(db, user_id=user_id)
    window_seconds = int(settings.AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS)
    max_failures = int(settings.AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT)

    window_started = _as_utc(row.failed_login_window_started_at)
    if window_started is None or current - window_started > timedelta(seconds=window_seconds):
        row.failed_login_window_started_at = current
        row.failed_login_count = 1
    else:
        row.failed_login_count += 1

    if row.failed_login_count >= max_failures:
        row.locked_until = current + timedelta(seconds=window_seconds)
    row.updated_at = current
    db.add(row)
    db.flush()
    return row


def clear_failures(db: Session, *, user_id: uuid.UUID, now: datetime | None = None) -> None:
    current = now or datetime.now(UTC)
    row = get_or_create_for_update(db, user_id=user_id)
    row.failed_login_count = 0
    row.failed_login_window_started_at = None
    row.locked_until = None
    row.last_login_at = current
    row.updated_at = current
    db.add(row)
    db.flush()
