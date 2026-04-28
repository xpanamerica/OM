"""AI 任务：创建权限与查询（执行委托 Mock worker）。"""

from __future__ import annotations

import uuid

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.ai_codes import AI_JOB_CREATE_FORBIDDEN, AI_JOB_INVALID_TYPE, AI_JOB_NOT_FOUND
from app.core.exceptions import AppError
from app.core.video_codes import VIDEO_NOT_FOUND
from app.models.enums import AiJobType, UserRole
from app.models.user import User
from app.repositories import ai_job_repository, video_repository
from app.schemas.ai_job import AiJobCreate
from app.services.ai_job_worker import execute_mock_ai_job


def _video_or_404(db: Session, video_id: uuid.UUID):
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    return v


def _parse_job_type(raw: str) -> AiJobType:
    try:
        return AiJobType(raw)
    except ValueError:
        raise AppError(
            "job_type 无效",
            status_code=400,
            code=AI_JOB_INVALID_TYPE,
        ) from None


def assert_can_manage_jobs_for_video(video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id == actor.id:
        return
    raise AppError("无权为该视频创建 AI 任务", status_code=403, code=AI_JOB_CREATE_FORBIDDEN)


def assert_can_view_job_for_video(video, actor: User) -> None:
    """与创建权限一致；无权限时 404，避免泄露资源存在。"""
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id == actor.id:
        return
    raise AppError("AI 任务不存在", status_code=404, code=AI_JOB_NOT_FOUND)


def create_job(
    db: Session,
    actor: User,
    video_id: uuid.UUID,
    payload: AiJobCreate,
    background_tasks: BackgroundTasks,
):
    video = _video_or_404(db, video_id)
    assert_can_manage_jobs_for_video(video, actor)
    jt = _parse_job_type(payload.job_type)
    row = ai_job_repository.create(db, video_id=video_id, job_type=jt, input_payload=payload.input_payload)
    db.commit()
    db.refresh(row)
    background_tasks.add_task(execute_mock_ai_job, row.id)
    return row


def get_job(db: Session, actor: User, job_id: uuid.UUID):
    row = ai_job_repository.get_by_id(db, job_id)
    if row is None:
        raise AppError("AI 任务不存在", status_code=404, code=AI_JOB_NOT_FOUND)
    video = _video_or_404(db, row.video_id)
    assert_can_view_job_for_video(video, actor)
    return row


def list_jobs_for_video(db: Session, actor: User, video_id: uuid.UUID, *, offset: int, limit: int):
    video = _video_or_404(db, video_id)
    assert_can_view_job_for_video(video, actor)
    total = ai_job_repository.count_by_video(db, video_id)
    items = ai_job_repository.list_by_video(db, video_id, offset=offset, limit=limit)
    return items, total
