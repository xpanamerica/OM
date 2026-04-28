"""阶段 14：视频—概念绑定（管理员写；按视频可见性读）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response

from app.api.deps import DbSession
from app.api.dependencies.auth import OptionalUser, require_admin
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.concept import VideoConceptPublic, VideoConceptsPut
from app.services import concept_service

router = APIRouter()


@router.get(
    "/{video_id}/concepts",
    response_model=list[VideoConceptPublic],
    summary="视频关联的概念",
    description="需能查看该视频（与 ``GET /videos/{id}`` 可见性一致）。",
)
def list_video_concepts(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    video_id: uuid.UUID,
):
    pairs = concept_service.list_concepts_for_video(db, optional_user, video_id)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    out: list[VideoConceptPublic] = []
    for vc, c in pairs:
        out.append(
            VideoConceptPublic(
                concept_id=c.id,
                concept_name=c.name,
                start_time_seconds=vc.start_time_seconds,
                end_time_seconds=vc.end_time_seconds,
            )
        )
    return out


@router.put(
    "/{video_id}/concepts",
    status_code=204,
    summary="替换视频的概念绑定",
    description="需管理员；整表替换为请求体中的列表。",
    dependencies=[Depends(require_admin), Depends(set_mutation_cache_control)],
)
def put_video_concepts(db: DbSession, video_id: uuid.UUID, body: VideoConceptsPut) -> Response:
    concept_service.replace_video_concepts(db, video_id, body)
    return Response(status_code=204)
