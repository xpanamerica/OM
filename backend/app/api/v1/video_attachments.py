"""稿件附属文件：作者/管理员上传与下载。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import DbSession
from app.api.dependencies.auth import CurrentUser
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.schemas.video_attachment import VideoAttachmentOut
from app.services import video_attachment_service

router = APIRouter()


@router.post(
    "/{video_id}/attachments",
    response_model=VideoAttachmentOut,
    status_code=201,
    summary="上传稿件附件",
    description=(
        "需登录。**作者或管理员**可为指定稿件上传图片、PDF、Office 等附属文件；"
        "扩展名与大小受环境变量 ``ALLOWED_ATTACHMENT_EXTENSIONS`` / ``MAX_ATTACHMENT_SIZE_MB`` 约束；"
        "默认启用文件头魔数与扩展名交叉校验（``ATTACHMENT_VERIFY_FILE_MAGIC``，错误码 ``UPLOAD_ATTACHMENT_MAGIC_MISMATCH``）。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_video_attachment(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="附件二进制流")],
) -> VideoAttachmentOut:
    return await video_attachment_service.save_attachment(db, actor=current_user, video_id=video_id, upload=file)


@router.get(
    "/{video_id}/attachments",
    response_model=list[VideoAttachmentOut],
    summary="列出稿件附件",
    description="需登录；仅 **作者或管理员** 可列出该稿件的附属文件元数据。",
)
def list_video_attachments(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
) -> list[VideoAttachmentOut]:
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return video_attachment_service.list_attachments(db, actor=current_user, video_id=video_id)


@router.get(
    "/{video_id}/attachments/{attachment_id}/file",
    summary="下载稿件附件",
    description="需登录；仅 **作者或管理员** 可下载原始文件。",
    response_class=FileResponse,
)
def download_video_attachment(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> FileResponse:
    path, download_name, media_type = video_attachment_service.attachment_file_path(
        db, actor=current_user, video_id=video_id, attachment_id=attachment_id
    )
    return FileResponse(
        path=str(path),
        filename=download_name,
        media_type=media_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, no-store, max-age=0, must-revalidate",
        },
    )
