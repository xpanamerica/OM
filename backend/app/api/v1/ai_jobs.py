"""阶段 15：按任务 ID 查询 AI 任务。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.api.deps import DbSession
from app.api.dependencies.auth import CurrentUser
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL
from app.schemas.ai_job import AiJobPublic
from app.services import ai_job_service

router = APIRouter()


@router.get(
    "/{job_id}",
    response_model=AiJobPublic,
    summary="获取 AI 任务详情",
    description=(
        "仅当对关联视频有「作者或管理员」权限时可查看；否则 404（不暴露存在性）。"
        "``status``：``pending`` → ``processing``（running）→ ``completed``（success）或 ``failed``。"
    ),
)
def get_ai_job(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    job_id: uuid.UUID,
) -> AiJobPublic:
    row = ai_job_service.get_job(db, current_user, job_id)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return AiJobPublic.model_validate(row)
