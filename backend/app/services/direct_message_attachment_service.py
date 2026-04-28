from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.direct_message import DirectMessageAttachment
from app.models.user import User
from app.repositories import user_repository
from app.schemas.social import DirectMessageAttachmentOut
from app.services import social_service

MAX_DIRECT_MESSAGE_ATTACHMENT_BYTES = 20 * 1024 * 1024
ALLOWED_DIRECT_MESSAGE_ATTACHMENT_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "txt",
    "md",
    "pdf",
    "doc",
    "docx",
}


def _storage_dir() -> Path:
    root = Path("data/direct_message_attachments").expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def _sanitize_original_filename(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.replace("\x00", "")
    base = re.sub(r"[\r\n\t]", "_", base).strip()
    return (base[:255] if base else "file") or "file"


def _extension(name: str) -> str:
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower().strip()


def _attachment_out(row: DirectMessageAttachment) -> DirectMessageAttachmentOut:
    return DirectMessageAttachmentOut(
        id=row.id,
        original_filename=row.original_filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        url=f"{settings.API_V1_PREFIX}/direct-messages/attachments/{row.id}/file",
        created_at=row.created_at,
    )


async def save_attachment(
    db: Session,
    *,
    actor: User,
    peer_id: uuid.UUID,
    upload: UploadFile,
) -> DirectMessageAttachmentOut:
    peer = user_repository.get_by_id(db, peer_id)
    if peer is None:
        raise AppError("用户不存在", status_code=404)
    if actor.id == peer.id:
        raise AppError("不能给自己发送附件", status_code=400)
    if not social_service.can_send_message(db, sender=actor, recipient=peer):
        raise AppError("对方设置了私信权限", status_code=403)

    safe_name = _sanitize_original_filename(upload.filename or "file")
    ext = _extension(safe_name)
    if ext not in ALLOWED_DIRECT_MESSAGE_ATTACHMENT_EXTENSIONS:
        raise AppError("仅支持图片、PDF、Word、Markdown 与文本附件", status_code=400)

    storage_key = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    root = _storage_dir()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / storage_key

    total = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DIRECT_MESSAGE_ATTACHMENT_BYTES:
                    raise AppError("私信附件大小不能超过 20MB", status_code=400)
                f.write(chunk)
    except AppError:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise
    except OSError as e:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise AppError(f"无法写入私信附件：{e}", status_code=500) from e

    if total == 0:
        dest.unlink(missing_ok=True)
        raise AppError("附件不能为空文件", status_code=400)

    content_type = (upload.content_type or "").strip() or mimetypes.guess_type(safe_name, strict=False)[0]
    row = DirectMessageAttachment(
        uploader_id=actor.id,
        peer_id=peer.id,
        original_filename=safe_name,
        content_type=content_type,
        size_bytes=total,
        storage_filename=storage_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _attachment_out(row)


def attachment_file_path(db: Session, *, actor: User, attachment_id: uuid.UUID) -> tuple[Path, str, str | None]:
    stmt = select(DirectMessageAttachment).where(
        DirectMessageAttachment.id == attachment_id,
        or_(DirectMessageAttachment.uploader_id == actor.id, DirectMessageAttachment.peer_id == actor.id),
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise AppError("附件不存在", status_code=404)

    root = _storage_dir()
    path = root / row.storage_filename
    if not path.is_file():
        raise AppError("附件文件缺失", status_code=404)
    try:
        if path.resolve().parent != root.resolve():
            raise AppError("附件路径非法", status_code=500)
    except OSError:
        raise AppError("附件路径非法", status_code=500) from None
    return path, row.original_filename, row.content_type
