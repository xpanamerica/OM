from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video_like import VideoLike


def exists(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(VideoLike.id).where(VideoLike.user_id == user_id, VideoLike.video_id == video_id).limit(1)
        )
        is not None
    )


def create(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> VideoLike:
    row = VideoLike(user_id=user_id, video_id=video_id)
    db.add(row)
    db.flush()
    return row


def delete_if_exists(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    row = db.scalar(select(VideoLike).where(VideoLike.user_id == user_id, VideoLike.video_id == video_id))
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True
