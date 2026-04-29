from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.invite_code import InviteCode


def normalize_code(raw: str) -> str:
    return raw.strip().upper()


def get_by_code_for_update(db: Session, raw_code: str) -> InviteCode | None:
    code = normalize_code(raw_code)
    if not code:
        return None
    stmt = select(InviteCode).where(InviteCode.code == code).with_for_update()
    return db.scalars(stmt).first()


def create_invite(
    db: Session,
    *,
    code: str,
    created_by: uuid.UUID | None,
    expires_at: datetime | None,
    max_uses: int,
) -> InviteCode:
    row = InviteCode(
        code=normalize_code(code),
        created_by=created_by,
        expires_at=expires_at,
        max_uses=max_uses,
        used_count=0,
        status="active",
    )
    db.add(row)
    db.flush()
    return row


def list_invite_codes(db: Session, *, offset: int, limit: int) -> tuple[list[InviteCode], int]:
    total = int(db.scalar(select(func.count()).select_from(InviteCode)) or 0)
    rows = list(
        db.scalars(
            select(InviteCode).order_by(InviteCode.created_at.desc()).offset(offset).limit(limit)
        ).all()
    )
    return rows, total
