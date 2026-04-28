"""阶段 12：upload_intents 写入。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.upload_intent import UploadIntent


def exists_intent_for_user_and_vod_video_id(db: Session, *, user_id: uuid.UUID, vod_video_id: str) -> bool:
    vid = (vod_video_id or "").strip()
    if not vid:
        return False
    stmt = select(UploadIntent.id).where(UploadIntent.user_id == user_id, UploadIntent.vod_video_id == vid).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None


def create_intent(
    db: Session,
    *,
    user_id: uuid.UUID,
    filename: str,
    file_size: int,
    vod_video_id: str,
    status: str = "issued",
) -> UploadIntent:
    row = UploadIntent(
        user_id=user_id,
        filename=filename,
        file_size=file_size,
        vod_video_id=vod_video_id,
        status=status,
    )
    db.add(row)
    db.flush()
    return row
