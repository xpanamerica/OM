from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.video import Video
from app.models.view_record import ViewRecord


def get_by_user_and_video(db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID) -> ViewRecord | None:
    return db.scalar(select(ViewRecord).where(ViewRecord.user_id == user_id, ViewRecord.video_id == video_id))


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    video_id: uuid.UUID,
    progress_seconds: int,
    last_viewed_at: datetime,
) -> ViewRecord:
    row = ViewRecord(
        user_id=user_id,
        video_id=video_id,
        progress_seconds=progress_seconds,
        last_viewed_at=last_viewed_at,
    )
    db.add(row)
    db.flush()
    return row


def update_progress(
    db: Session,
    row: ViewRecord,
    *,
    progress_seconds: int,
    last_viewed_at: datetime,
) -> ViewRecord:
    row.progress_seconds = progress_seconds
    row.last_viewed_at = last_viewed_at
    db.add(row)
    db.flush()
    return row


def list_by_user_page(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
    cursor_before: tuple[datetime, uuid.UUID] | None,
) -> tuple[list[tuple[ViewRecord, str | None]], int]:
    """列表 + 总条数；每条附带 ``videos.title``（内连接，与 FK 一致）。"""
    base = ViewRecord.user_id == user_id
    if cursor_before is not None:
        cut_t, cut_id = cursor_before
        where_clause = and_(
            base,
            or_(
                ViewRecord.last_viewed_at < cut_t,
                and_(ViewRecord.last_viewed_at == cut_t, ViewRecord.id < cut_id),
            ),
        )
        off = 0
    else:
        where_clause = base
        off = int(offset)

    stmt = (
        select(ViewRecord, Video.title, func.count().over().label("_total"))
        .join(Video, Video.id == ViewRecord.video_id)
        .where(where_clause)
        .order_by(ViewRecord.last_viewed_at.desc(), ViewRecord.id.desc())
        .offset(off)
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    if not rows:
        total = int(
            db.scalar(select(func.count()).select_from(ViewRecord).where(ViewRecord.user_id == user_id)) or 0
        )
        return [], total
    items = [(r[0], r[1]) for r in rows]
    total = int(rows[0]._total)
    return items, total
