"""稿件附属文件：作者/管理员上传至本地目录。"""

from __future__ import annotations

import mimetypes
import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.core import upload_security
from app.core import attachment_upload_rate_limit
from app.core.upload_codes import (
    UPLOAD_ATTACHMENT_FILE_TOO_LARGE,
    UPLOAD_ATTACHMENT_INSUFFICIENT_DISK,
)
from app.core.video_codes import (
    VIDEO_ATTACHMENT_FORBIDDEN,
    VIDEO_ATTACHMENT_NOT_FOUND,
    VIDEO_ATTACHMENT_TOO_MANY,
    VIDEO_NOT_FOUND,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import video_attachment_repository, video_repository


def _sanitize_original_filename(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.replace("\x00", "")
    base = re.sub(r"[\r\n\t]", "_", base).strip()
    return (base[:255] if base else "file") or "file"


def _storage_dir() -> Path:
    p = Path(settings.ATTACHMENT_STORAGE_DIR).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _assert_author_or_admin(video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id != actor.id:
        raise AppError("仅作者或管理员可管理附件", status_code=403, code=VIDEO_ATTACHMENT_FORBIDDEN)


async def save_attachment(
    db: Session,
    *,
    actor: User,
    video_id: uuid.UUID,
    upload: UploadFile,
) -> "VideoAttachmentOut":
    from app.schemas.video_attachment import VideoAttachmentOut

    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)
    attachment_upload_rate_limit.consume_attachment_post_slot_or_raise(user_id=actor.id)

    raw_name = upload.filename or "file"
    safe_name = _sanitize_original_filename(raw_name)
    upload_security.assert_attachment_upload_ok(filename=safe_name, declared_size=None)

    n_existing = video_attachment_repository.count_for_video(db, video_id)
    if n_existing >= settings.MAX_ATTACHMENTS_PER_VIDEO:
        raise AppError(
            f"附件数量已达上限（{settings.MAX_ATTACHMENTS_PER_VIDEO}）",
            status_code=400,
            code=VIDEO_ATTACHMENT_TOO_MANY,
        )

    ext = upload_security.filename_extension(safe_name)
    storage_key = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    root = _storage_dir()
    root.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    reserve_b = settings.ATTACHMENT_MIN_RESERVED_DISK_MB * 1024 * 1024
    if reserve_b > 0:
        need_free = reserve_b + max_bytes
        try:
            usage = shutil.disk_usage(str(root.resolve()))
        except OSError as e:
            raise AppError(
                f"无法检测附件存储磁盘空间：{e}",
                status_code=500,
                code="ATTACHMENT_DISK_CHECK_FAILED",
            ) from e
        if usage.free < need_free:
            raise AppError(
                f"存储空间不足（需预留约 {settings.ATTACHMENT_MIN_RESERVED_DISK_MB} MB + 单附件上限）。"
                "请清理磁盘或调整 ATTACHMENT_STORAGE_DIR / ATTACHMENT_MIN_RESERVED_DISK_MB。",
                status_code=507,
                code=UPLOAD_ATTACHMENT_INSUFFICIENT_DISK,
            )

    dest = root / storage_key
    total = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        f"附件大小超过上限（{settings.MAX_ATTACHMENT_SIZE_MB} MB）",
                        status_code=400,
                        code=UPLOAD_ATTACHMENT_FILE_TOO_LARGE,
                    )
                f.write(chunk)
    except AppError:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        raise
    except OSError as e:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        raise AppError(f"无法写入附件存储：{e}", status_code=500, code="ATTACHMENT_STORAGE_WRITE_FAILED") from e

    if total == 0:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        raise AppError("附件不能为空文件", status_code=400, code="ATTACHMENT_EMPTY_FILE")

    upload_security.assert_attachment_upload_ok(filename=safe_name, declared_size=total)

    if settings.ATTACHMENT_VERIFY_FILE_MAGIC:
        from app.core import attachment_magic

        try:
            attachment_magic.assert_attachment_file_magic_matches_extension(file_path=dest, ext=ext or "")
        except AppError:
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            raise

    raw_ct = (upload.content_type or "").strip() or None
    ct = raw_ct
    if not ct or ct == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(safe_name, strict=False)
        if guessed:
            ct = guessed
    if not ct:
        ct = None
    row = video_attachment_repository.create_row(
        db,
        video_id=video_id,
        uploader_id=actor.id,
        original_filename=safe_name,
        content_type=ct,
        size_bytes=total,
        storage_filename=storage_key,
    )
    db.commit()
    db.refresh(row)
    return VideoAttachmentOut.model_validate(row)


def list_attachments(db: Session, *, actor: User, video_id: uuid.UUID) -> list["VideoAttachmentOut"]:
    from app.schemas.video_attachment import VideoAttachmentOut

    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)
    rows = video_attachment_repository.list_for_video(db, video_id)
    return [VideoAttachmentOut.model_validate(r) for r in rows]


def attachment_file_path(db: Session, *, actor: User, video_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[Path, str, str | None]:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)
    row = video_attachment_repository.get_by_id_for_video(db, video_id, attachment_id)
    if row is None:
        raise AppError("附件不存在", status_code=404, code=VIDEO_ATTACHMENT_NOT_FOUND)
    root = _storage_dir()
    path = root / row.storage_filename
    if not path.is_file():
        raise AppError("附件文件缺失", status_code=404, code=VIDEO_ATTACHMENT_NOT_FOUND)
    try:
        if path.resolve().parent != root.resolve():
            raise AppError("附件路径非法", status_code=500, code="ATTACHMENT_PATH_INVALID")
    except OSError:
        raise AppError("附件路径非法", status_code=500, code="ATTACHMENT_PATH_INVALID") from None
    return path, row.original_filename, row.content_type
