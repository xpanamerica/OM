from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.registration_attempt import RegistrationAttempt

_log = logging.getLogger("app.registration_audit")


def record_registration_attempt(
    *,
    ip_address: str,
    user_agent: str | None,
    email: str | None,
    username: str | None,
    invite_code_submitted: str | None,
    success: bool,
    failure_reason: str | None,
    created_user_id: uuid.UUID | None,
) -> None:
    """独立会话写入，避免主注册事务回滚导致审计丢失。"""
    row = RegistrationAttempt(
        ip_address=ip_address[:64],
        user_agent=user_agent,
        email=(email[:255] if email else None),
        username=(username[:64] if username else None),
        invite_code_submitted=(invite_code_submitted[:128] if invite_code_submitted else None),
        success=success,
        failure_reason=failure_reason,
        created_user_id=created_user_id,
    )
    try:
        with SessionLocal() as db:
            db.add(row)
            db.commit()
    except Exception:
        _log.exception("registration_attempt_persist_failed")


def list_registration_attempts(
    db: Session, *, offset: int, limit: int
) -> tuple[list[RegistrationAttempt], int]:
    total = int(db.scalar(select(func.count()).select_from(RegistrationAttempt)) or 0)
    rows = list(
        db.scalars(
            select(RegistrationAttempt)
            .order_by(RegistrationAttempt.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total
