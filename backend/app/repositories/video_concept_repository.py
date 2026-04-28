from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.concept import Concept, VideoConcept
from app.models.enums import VideoStatus
from app.models.video import Video


def list_for_video(db: Session, video_id: uuid.UUID) -> list[tuple[VideoConcept, Concept]]:
    stmt = (
        select(VideoConcept, Concept)
        .join(Concept, Concept.id == VideoConcept.concept_id)
        .where(VideoConcept.video_id == video_id)
        .order_by(Concept.name.asc(), Concept.id.asc())
    )
    return list(db.execute(stmt).all())


def count_published_videos_for_concept(db: Session, *, concept_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(VideoConcept)
            .join(Video, Video.id == VideoConcept.video_id)
            .where(VideoConcept.concept_id == concept_id, Video.status == VideoStatus.PUBLISHED)
        )
        or 0
    )


def list_published_videos_for_concept(
    db: Session, *, concept_id: uuid.UUID, offset: int, limit: int
) -> list[tuple[Video, VideoConcept]]:
    stmt = (
        select(Video, VideoConcept)
        .options(selectinload(Video.tags))
        .join(VideoConcept, VideoConcept.video_id == Video.id)
        .where(VideoConcept.concept_id == concept_id, Video.status == VideoStatus.PUBLISHED)
        .order_by(Video.published_at.desc().nulls_last(), Video.created_at.desc(), Video.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).all())


def replace_for_video(
    db: Session,
    video_id: uuid.UUID,
    *,
    links: list[tuple[uuid.UUID, int | None, int | None]],
) -> None:
    db.execute(delete(VideoConcept).where(VideoConcept.video_id == video_id))
    for concept_id, start_s, end_s in links:
        db.add(
            VideoConcept(
                video_id=video_id,
                concept_id=concept_id,
                start_time_seconds=start_s,
                end_time_seconds=end_s,
            )
        )
    db.flush()
