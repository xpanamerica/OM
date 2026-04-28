from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_block import UserBlock


def exists(db: Session, *, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> bool:
    stmt = select(func.count()).select_from(UserBlock).where(
        UserBlock.blocker_id == blocker_id,
        UserBlock.blocked_id == blocked_id,
    )
    return int(db.execute(stmt).scalar_one()) > 0


def any_between(db: Session, *, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
    stmt = select(func.count()).select_from(UserBlock).where(
        or_(
            (UserBlock.blocker_id == user_a) & (UserBlock.blocked_id == user_b),
            (UserBlock.blocker_id == user_b) & (UserBlock.blocked_id == user_a),
        )
    )
    return int(db.execute(stmt).scalar_one()) > 0


def create(db: Session, *, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> UserBlock:
    row = UserBlock(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(row)
    db.flush()
    return row


def delete_pair(db: Session, *, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> int:
    res = db.execute(
        delete(UserBlock).where(UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id)
    )
    return int(res.rowcount or 0)


def list_blocked(db: Session, *, blocker_id: uuid.UUID, offset: int, limit: int) -> list[tuple[User, UserBlock]]:
    stmt = (
        select(User, UserBlock)
        .join(UserBlock, User.id == UserBlock.blocked_id)
        .where(UserBlock.blocker_id == blocker_id, User.deleted_at.is_(None))
        .order_by(UserBlock.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(u, b) for u, b in db.execute(stmt).all()]
