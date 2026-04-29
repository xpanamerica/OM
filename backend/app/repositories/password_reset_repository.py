from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken


def delete_unused_for_user(db: Session, *, user_id: uuid.UUID) -> None:
    db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    db.flush()


def insert_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> PasswordResetToken:
    row = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def get_active_by_token_hash(
    db: Session,
    *,
    token_hash: str,
    now: datetime | None = None,
) -> PasswordResetToken | None:
    t = now or datetime.now(UTC)
    stmt = (
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > t,
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def mark_used(db: Session, *, token_id: uuid.UUID, used_at: datetime | None = None) -> None:
    when = used_at or datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token_id)
        .values(used_at=when)
    )
    db.flush()
