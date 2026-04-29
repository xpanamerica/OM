from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.invite_code import InviteCode
from app.models.user import User
from app.repositories import invite_code_repository
from app.schemas.invite_codes import (
    AdminInviteCodeCreate,
    AdminInviteCodeCreated,
    AdminInviteCodeItem,
    AdminInviteCodeListOut,
)


def _to_item(row: InviteCode) -> AdminInviteCodeItem:
    return AdminInviteCodeItem(
        id=row.id,
        code=row.code,
        created_by=row.created_by,
        used_by=row.used_by,
        used_at=row.used_at,
        expires_at=row.expires_at,
        max_uses=row.max_uses,
        used_count=row.used_count,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_invite_codes(db: Session, *, offset: int, limit: int) -> AdminInviteCodeListOut:
    rows, total = invite_code_repository.list_invite_codes(db, offset=offset, limit=limit)
    return AdminInviteCodeListOut(items=[_to_item(r) for r in rows], total=total)


def create_invite_code(db: Session, admin: User, body: AdminInviteCodeCreate) -> AdminInviteCodeCreated:
    # 96-bit 随机性（24 hex）；较 16 hex 更难枚举
    raw = secrets.token_hex(12).upper()
    row = invite_code_repository.create_invite(
        db,
        code=raw,
        created_by=admin.id,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
    )
    db.commit()
    db.refresh(row)
    return AdminInviteCodeCreated(invite=_to_item(row))


def revoke_invite_code(db: Session, invite_id: uuid.UUID) -> AdminInviteCodeItem:
    row = db.get(InviteCode, invite_id)
    if row is None:
        raise AppError("邀请码不存在", status_code=404)
    if row.status != "active":
        raise AppError("仅可作废仍处于启用状态的邀请码", status_code=400)
    row.status = "revoked"
    db.commit()
    db.refresh(row)
    return _to_item(row)
