from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.user_mfa_setting import UserMfaSetting


def get(db: Session, *, user_id: uuid.UUID) -> UserMfaSetting | None:
    return db.get(UserMfaSetting, user_id)


def get_or_create(db: Session, *, user_id: uuid.UUID) -> UserMfaSetting:
    row = db.get(UserMfaSetting, user_id)
    if row is not None:
        return row
    row = UserMfaSetting(user_id=user_id)
    db.add(row)
    db.flush()
    return row


def save_pending_secret(db: Session, *, user_id: uuid.UUID, sealed_secret: str) -> UserMfaSetting:
    row = get_or_create(db, user_id=user_id)
    row.totp_secret_sealed = sealed_secret
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.flush()
    return row


def enable(
    db: Session,
    *,
    user_id: uuid.UUID,
    sealed_secret: str,
    recovery_code_hashes_json: str,
) -> UserMfaSetting:
    now = datetime.now(UTC)
    row = get_or_create(db, user_id=user_id)
    row.totp_secret_sealed = sealed_secret
    row.enabled = True
    row.enabled_at = now
    row.recovery_code_hashes_json = recovery_code_hashes_json
    row.updated_at = now
    db.add(row)
    db.flush()
    return row


def disable(db: Session, *, user_id: uuid.UUID) -> None:
    row = get_or_create(db, user_id=user_id)
    row.enabled = False
    row.enabled_at = None
    row.totp_secret_sealed = None
    row.recovery_code_hashes_json = None
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.flush()


def update_recovery_hashes(db: Session, *, user_id: uuid.UUID, recovery_code_hashes_json: str) -> None:
    row = get_or_create(db, user_id=user_id)
    row.recovery_code_hashes_json = recovery_code_hashes_json
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.flush()
