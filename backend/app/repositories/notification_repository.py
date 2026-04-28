from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user_notification import UserNotification


def count_for_user(db: Session, *, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(UserNotification).where(UserNotification.user_id == user_id)
    return int(db.execute(stmt).scalar_one())


def count_unread(db: Session, *, user_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(UserNotification)
        .where(UserNotification.user_id == user_id, UserNotification.read_at.is_(None))
    )
    return int(db.execute(stmt).scalar_one())


def list_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[UserNotification], int]:
    total_stmt = select(func.count()).select_from(UserNotification).where(UserNotification.user_id == user_id)
    total = int(db.execute(total_stmt).scalar_one())
    stmt = (
        select(UserNotification)
        .where(UserNotification.user_id == user_id)
        .order_by(UserNotification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    return rows, total


def get_for_user(
    db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID
) -> UserNotification | None:
    stmt = select(UserNotification).where(
        UserNotification.id == notification_id,
        UserNotification.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, row: UserNotification) -> UserNotification:
    db.add(row)
    db.flush()
    return row
