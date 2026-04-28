"""公开封面图：``GET /covers/{video_id}.jpg``（与 ``videos.cover_url`` 对应）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from starlette.responses import FileResponse

from app.api.deps import DbSession
from app.api.dependencies.auth import OptionalUser
from app.services import video_cover_service

router = APIRouter()


@router.get(
    "/covers/{video_id}.jpg",
    summary="读取稿件封面图",
    description="``videos.cover_url`` 指向本路径时由前端 ``<img>`` 引用；**已发布**任意访问，**未发布**仅作者或管理员。",
    response_class=FileResponse,
)
def get_video_cover_image(
    db: DbSession,
    video_id: uuid.UUID,
    optional_user: OptionalUser,
) -> FileResponse:
    path = video_cover_service.resolve_cover_disk_path(db, video_id=video_id, viewer=optional_user)
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"{video_id}.jpg",
        content_disposition_type="inline",
    )
