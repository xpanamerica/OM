"""稿件封面：落盘 + 公开读取（列表/首页展示）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_security import filename_extension
from app.core.video_codes import VIDEO_EDIT_FORBIDDEN, VIDEO_NOT_FOUND
from app.models.enums import UserRole
from app.models.user import User
from app.models.video import Video
from app.repositories import video_repository
from app.services import video_service

_COVER_SUFFIX = ".jpg"


def _root() -> Path:
    p = Path(settings.VIDEO_COVER_STORAGE_DIR).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def cover_file_path(video_id: uuid.UUID) -> Path:
    return _root() / f"{video_id}{_COVER_SUFFIX}"


def cover_public_path(video_id: uuid.UUID) -> str:
    """存入 ``videos.cover_url`` 的相对路径（与 ``API_V1_PREFIX`` 拼接后由前端请求）。"""
    prefix = settings.API_V1_PREFIX.strip().rstrip("/")
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return f"{prefix}/covers/{video_id}{_COVER_SUFFIX}"


def _assert_author_or_admin(video: Video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id != actor.id:
        raise AppError("仅作者或管理员可上传封面", status_code=403, code=VIDEO_EDIT_FORBIDDEN)


async def save_cover_upload(
    db: Session,
    *,
    actor: User,
    video_id: uuid.UUID,
    upload: UploadFile,
) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not video_service.can_view_video(v, actor):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)

    raw_name = upload.filename or "cover.jpg"
    ext = filename_extension(raw_name)
    if ext not in ("jpg", "jpeg"):
        raise AppError("封面须为 .jpg / .jpeg 文件", status_code=400, code="VIDEO_COVER_EXTENSION_NOT_ALLOWED")

    ct = (upload.content_type or "").strip().lower()
    if ct not in ("image/jpeg", "image/jpg", "application/octet-stream", ""):
        raise AppError("封面须为 JPEG（前端可将截图导出为 JPEG）", status_code=400, code="VIDEO_COVER_BAD_MIME")

    max_b = int(settings.VIDEO_COVER_MAX_UPLOAD_MB) * 1024 * 1024
    dest = cover_file_path(video_id)
    total = 0
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = await upload.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_b:
                    raise AppError(
                        f"封面超过上限 {settings.VIDEO_COVER_MAX_UPLOAD_MB} MB",
                        status_code=400,
                        code="VIDEO_COVER_TOO_LARGE",
                    )
                out.write(chunk)
    except AppError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise

    if total == 0:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise AppError("封面文件为空", status_code=400, code="VIDEO_COVER_EMPTY")

    head = tmp.read_bytes()[:16]
    if not head.startswith(b"\xff\xd8\xff"):
        try:
            tmp.unlink()
        except OSError:
            pass
        raise AppError("文件内容与扩展名不符或不是有效图片", status_code=400, code="VIDEO_COVER_BAD_CONTENT")

    tmp.replace(dest)

    v.cover_url = cover_public_path(video_id)
    v.updated_at = datetime.now(timezone.utc)
    db.commit()
    out = video_repository.get_by_id(db, video_id, load_tags=True)
    assert out is not None
    return out


def resolve_cover_disk_path(db: Session, *, video_id: uuid.UUID, viewer: User | None) -> Path:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not video_service.can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    p = cover_file_path(video_id)
    if not p.is_file():
        raise AppError("封面不存在", status_code=404, code="VIDEO_COVER_NOT_FOUND")
    return p
