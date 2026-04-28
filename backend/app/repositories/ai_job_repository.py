from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_job import AiJob
from app.models.enums import AiJobStatus, AiJobType


def create(
    db: Session,
    *,
    video_id: uuid.UUID,
    job_type: AiJobType,
    input_payload: dict[str, Any] | None,
) -> AiJob:
    row = AiJob(
        video_id=video_id,
        job_type=job_type,
        status=AiJobStatus.PENDING,
        input_payload=input_payload,
        output_payload=None,
        error_message=None,
    )
    db.add(row)
    db.flush()
    return row


def get_by_id(db: Session, job_id: uuid.UUID) -> AiJob | None:
    return db.execute(select(AiJob).where(AiJob.id == job_id)).scalar_one_or_none()


def count_by_video(db: Session, video_id: uuid.UUID) -> int:
    return int(
        db.scalar(select(func.count(AiJob.id)).select_from(AiJob).where(AiJob.video_id == video_id)) or 0
    )


def list_by_video(
    db: Session,
    video_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
) -> list[AiJob]:
    stmt = (
        select(AiJob)
        .where(AiJob.video_id == video_id)
        .order_by(AiJob.created_at.desc(), AiJob.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def save_row(db: Session, row: AiJob) -> None:
    db.add(row)
    db.flush()
