"""用户私信：会话列表、点对点消息列表与发送。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies.auth import CurrentUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.schemas.social import DirectConversationOut, DirectMessageAttachmentOut, DirectMessageCreate, DirectMessageOut
from app.services import direct_message_attachment_service, social_service

router = APIRouter()


@router.get("/conversations", response_model=list[DirectConversationOut], summary="我的私信会话")
def list_conversations(
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DirectConversationOut]:
    return social_service.list_conversations(db, current_user=current_user, offset=offset, limit=limit)


@router.get(
    "/conversations/{peer_id}/messages",
    response_model=list[DirectMessageOut],
    summary="与某用户的私信记录",
)
def list_messages(
    peer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[DirectMessageOut]:
    return social_service.list_messages_with_peer(
        db, current_user=current_user, peer_id=peer_id, offset=offset, limit=limit
    )


@router.post(
    "/conversations/{peer_id}/messages",
    response_model=DirectMessageOut,
    summary="发送私信",
    dependencies=[Depends(set_mutation_cache_control)],
)
def send_message(
    peer_id: UUID,
    payload: DirectMessageCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> DirectMessageOut:
    return social_service.send_direct_message(db, sender=current_user, recipient_id=peer_id, body=payload.body)


@router.post(
    "/conversations/{peer_id}/attachments",
    response_model=DirectMessageAttachmentOut,
    status_code=201,
    summary="上传私信附件",
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_attachment(
    peer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="图片或文本附件")],
) -> DirectMessageAttachmentOut:
    return await direct_message_attachment_service.save_attachment(db, actor=current_user, peer_id=peer_id, upload=file)


@router.get(
    "/attachments/{attachment_id}/file",
    summary="下载私信附件",
    response_class=FileResponse,
)
def download_attachment(
    attachment_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FileResponse:
    path, download_name, media_type = direct_message_attachment_service.attachment_file_path(
        db, actor=current_user, attachment_id=attachment_id
    )
    return FileResponse(
        path=str(path),
        filename=download_name,
        media_type=media_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store, max-age=0, must-revalidate"},
    )
