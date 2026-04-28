from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.video_attachment import VideoAttachment


def count_for_video(db: Session, video_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(VideoAttachment).where(VideoAttachment.video_id == video_id)
    return int(db.execute(stmt).scalar_one())


def create_row(
    db: Session,
    *,
    video_id: uuid.UUID,
    uploader_id: uuid.UUID,
    original_filename: str,
    content_type: str | None,
    size_bytes: int,
    storage_filename: str,
) -> VideoAttachment:
    row = VideoAttachment(
        video_id=video_id,
        uploader_id=uploader_id,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_filename=storage_filename,
    )
    db.add(row)
    db.flush()
    return row


def list_for_video(db: Session, video_id: uuid.UUID) -> list[VideoAttachment]:
    stmt = select(VideoAttachment).where(VideoAttachment.video_id == video_id).order_by(VideoAttachment.created_at)
    return list(db.scalars(stmt).all())


def get_by_id_for_video(db: Session, video_id: uuid.UUID, attachment_id: uuid.UUID) -> VideoAttachment | None:
    stmt = select(VideoAttachment).where(
        VideoAttachment.id == attachment_id,
        VideoAttachment.video_id == video_id,
    )
    return db.scalars(stmt).first()
