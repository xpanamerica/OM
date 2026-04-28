from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import VideoStatus
from app.models.video import Video
from app.models.video_favorite import VideoFavorite


def exists(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(VideoFavorite.id)
            .where(VideoFavorite.user_id == user_id, VideoFavorite.video_id == video_id)
            .limit(1)
        )
        is not None
    )


def create(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> VideoFavorite:
    row = VideoFavorite(user_id=user_id, video_id=video_id)
    db.add(row)
    db.flush()
    return row


def delete_if_exists(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    row = db.scalar(select(VideoFavorite).where(VideoFavorite.user_id == user_id, VideoFavorite.video_id == video_id))
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def count_published_favorites_by_user(db: Session, *, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(VideoFavorite)
            .join(Video, Video.id == VideoFavorite.video_id)
            .where(VideoFavorite.user_id == user_id, Video.status == VideoStatus.PUBLISHED)
        )
        or 0
    )


def list_published_favorite_videos_by_user(
    db: Session, *, user_id: uuid.UUID, offset: int, limit: int
) -> list[Video]:
    stmt = (
        select(Video)
        .options(selectinload(Video.tags))
        .join(VideoFavorite, VideoFavorite.video_id == Video.id)
        .where(VideoFavorite.user_id == user_id, Video.status == VideoStatus.PUBLISHED)
        .order_by(VideoFavorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    return list(rows)
