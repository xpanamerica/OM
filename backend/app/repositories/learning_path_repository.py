from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.user import User


def get_by_id(db: Session, path_id: uuid.UUID) -> LearningPath | None:
    return db.execute(select(LearningPath).where(LearningPath.id == path_id)).scalar_one_or_none()


def create(
    db: Session,
    *,
    title: str,
    description: str | None,
    creator_id: uuid.UUID,
    is_published: bool,
) -> LearningPath:
    row = LearningPath(
        title=title,
        description=description,
        creator_id=creator_id,
        is_published=is_published,
    )
    db.add(row)
    db.flush()
    return row


def list_paths(
    db: Session,
    *,
    viewer: User | None,
    offset: int,
    limit: int,
) -> tuple[list[LearningPath], int]:
    stmt = select(LearningPath)
    count_stmt = select(func.count()).select_from(LearningPath)

    if viewer is None:
        stmt = stmt.where(LearningPath.is_published.is_(True))
        count_stmt = count_stmt.where(LearningPath.is_published.is_(True))
    elif viewer.role == UserRole.ADMIN:
        pass
    else:
        vis = or_(LearningPath.is_published.is_(True), LearningPath.creator_id == viewer.id)
        stmt = stmt.where(vis)
        count_stmt = count_stmt.where(vis)

    total = int(db.scalar(count_stmt) or 0)
    stmt = stmt.order_by(LearningPath.created_at.desc(), LearningPath.id.desc()).offset(offset).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    return rows, total


def list_items(db: Session, path_id: uuid.UUID) -> list[LearningPathItem]:
    stmt = (
        select(LearningPathItem)
        .where(LearningPathItem.path_id == path_id)
        .order_by(LearningPathItem.order_index.asc(), LearningPathItem.video_id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def replace_items(
    db: Session,
    path_id: uuid.UUID,
    *,
    items: list[tuple[int, uuid.UUID, str | None]],
) -> None:
    """``items`` 元组为 ``(order_index, video_id, note)``。"""
    db.execute(delete(LearningPathItem).where(LearningPathItem.path_id == path_id))
    for order_index, video_id, note in items:
        db.add(
            LearningPathItem(
                path_id=path_id,
                order_index=order_index,
                video_id=video_id,
                note=note,
            )
        )
    db.flush()
