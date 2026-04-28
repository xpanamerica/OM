"""阶段 15：按视频创建 / 列出 AI 任务。"""

from __future__ import annotations

import uuid

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from app.api.deps import DbSession
from app.api.dependencies.auth import CurrentUser
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.ai_job import AiJobCreate, AiJobPublic
from app.services import ai_job_service

router = APIRouter()


@router.post(
    "/{video_id}/ai-jobs",
    response_model=AiJobPublic,
    status_code=201,
    summary="为视频创建 AI 任务",
    description=(
        "仅 **视频作者** 或 **管理员**。任务入队后由进程内 Mock 执行器异步处理（阶段 15 不接真实模型）。"
        "状态机：``pending`` → ``processing``（执行中，与常见「running」同义）→ ``completed``（成功，与「success」同义）或 ``failed``。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
def create_video_ai_job(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    body: AiJobCreate,
    background_tasks: BackgroundTasks,
) -> AiJobPublic:
    row = ai_job_service.create_job(db, current_user, video_id, body, background_tasks)
    return AiJobPublic.model_validate(row)


@router.get(
    "/{video_id}/ai-jobs",
    response_model=list[AiJobPublic],
    summary="列出某视频的 AI 任务",
    description=(
        "仅 **视频作者** 或 **管理员**；按创建时间倒序。"
        "各任务 ``status`` 含义见 ``POST .../ai-jobs`` 说明（``processing``/``completed`` 等）。"
    ),
)
def list_video_ai_jobs(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    items, total = ai_job_service.list_jobs_for_video(db, current_user, video_id, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return [AiJobPublic.model_validate(x) for x in items]
