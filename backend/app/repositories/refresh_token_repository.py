from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


def insert_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    ip_address: str | None,
    user_agent: str | None,
    user_agent_hash: str | None = None,
    device_label: str | None = None,
) -> RefreshToken:
    row = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=(ip_address[:64] if ip_address else None),
        user_agent=(user_agent[:512] if user_agent else None),
        user_agent_hash=user_agent_hash,
        device_label=(device_label[:128] if device_label else None),
    )
    db.add(row)
    db.flush()
    return row


def get_by_token_hash(db: Session, *, token_hash: str) -> RefreshToken | None:
    return db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).scalar_one_or_none()


def mark_used(db: Session, *, token_id: uuid.UUID, used_at: datetime | None = None) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id)
        .values(last_used_at=used_at or datetime.now(UTC))
    )
    db.flush()


def revoke_token(
    db: Session,
    *,
    token_id: uuid.UUID,
    replaced_by_token_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id)
        .values(
            revoked_at=revoked_at or datetime.now(UTC),
            replaced_by_token_id=replaced_by_token_id,
        )
    )
    db.flush()


def revoke_all_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    except_token_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
) -> int:
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    if except_token_id is not None:
        stmt = stmt.where(RefreshToken.id != except_token_id)
    result = db.execute(stmt.values(revoked_at=revoked_at or datetime.now(UTC)))
    db.flush()
    return int(result.rowcount or 0)


def delete_token(db: Session, *, token_id: uuid.UUID) -> int:
    result = db.execute(delete(RefreshToken).where(RefreshToken.id == token_id))
    db.flush()
    return int(result.rowcount or 0)


def list_active_for_user(db: Session, *, user_id: uuid.UUID, now: datetime | None = None) -> list[RefreshToken]:
    current = now or datetime.now(UTC)
    return list(
        db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > current,
            )
            .order_by(RefreshToken.last_used_at.desc().nullslast(), RefreshToken.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_active_for_user(db: Session, *, user_id: uuid.UUID, token_id: uuid.UUID) -> RefreshToken | None:
    return db.execute(
        select(RefreshToken).where(
            RefreshToken.id == token_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
