from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import case, func, or_, select, update
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


def redeem_invite_if_available(
    db: Session,
    *,
    invite_id: uuid.UUID,
    user_id: uuid.UUID,
    now: datetime,
) -> bool:
    """原子消费一次邀请码。

    ``SELECT ... FOR UPDATE`` 在 PostgreSQL 上足够，但 SQLite 测试环境会忽略行锁；
    条件 ``UPDATE`` 将「未用完才递增」变成数据库层不变量，避免并发请求双双成功。
    """
    stmt = (
        update(InviteCode)
        .where(
            InviteCode.id == invite_id,
            InviteCode.status == "active",
            InviteCode.used_count < InviteCode.max_uses,
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now),
        )
        .values(
            used_count=InviteCode.used_count + 1,
            used_by=user_id,
            used_at=now,
            updated_at=now,
            status=case(
                (InviteCode.used_count + 1 >= InviteCode.max_uses, "used"),
                else_="active",
            ),
        )
    )
    res = db.execute(stmt)
    db.flush()
    return bool(res.rowcount == 1)


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
