"""本机磁盘成片：上传、签发播放 URL、Range 流式输出。"""

from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.local_video_stream_token import sign_local_stream_token, verify_local_stream_token
from app.core.video_codes import (
    VIDEO_LOCAL_BAD_EXTENSION,
    VIDEO_LOCAL_FILE_MISSING,
    VIDEO_LOCAL_NOT_READY,
    VIDEO_LOCAL_PATH_INVALID,
    VIDEO_LOCAL_STREAM_TOKEN_INVALID,
    VIDEO_LOCAL_TOO_LARGE,
    VIDEO_LOCAL_UPLOAD_FORBIDDEN,
    VIDEO_NOT_FOUND,
)
from app.models.enums import UserRole, VodTranscodeStatus, VodUploadStatus
from app.models.user import User
from app.models.video import Video
from app.repositories import video_repository
from app.schemas.vod_play import VideoPlayResponse
from app.services import video_service

# multipart 读块与落盘缓冲：过小会导致 await/read 次数多、磁盘碎片写多；8MiB 在本地 SSD 上通常更稳。
_READ_WRITE_CHUNK_BYTES = 8 * 1024 * 1024


def _storage_root() -> Path:
    """与附件目录一致：相对路径相对进程工作目录（容器内一般为 ``/app``）。"""
    p = Path(settings.LOCAL_VIDEO_STORAGE_DIR).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def _allowed_suffixes() -> set[str]:
    raw = settings.ALLOWED_VIDEO_EXTENSIONS or ""
    out: set[str] = set()
    for part in raw.split(","):
        s = part.strip().lower().lstrip(".")
        if s:
            out.add(f".{s}")
    return out or {".mp4", ".webm", ".mov", ".mkv", ".m4v"}


def unlink_local_stored_media_by_relpath(relpath: str | None) -> None:
    """删除本机成片磁盘文件（若存在）；路径非法时静默跳过。"""
    rel = (relpath or "").strip()
    if not rel:
        return
    try:
        path = _abs_stored_path(rel)
    except AppError:
        return
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def _abs_stored_path(relpath: str) -> Path:
    rel = (relpath or "").strip().replace("\\", "/")
    if not rel or ".." in rel or rel.startswith("/"):
        raise AppError("本机媒资路径异常", status_code=500, code=VIDEO_LOCAL_PATH_INVALID)
    name = Path(rel).name
    root = _storage_root()
    full = (root / name).resolve()
    try:
        full.relative_to(root)
    except ValueError as e:
        raise AppError("本机媒资路径异常", status_code=500, code=VIDEO_LOCAL_PATH_INVALID) from e
    return full


def _guess_media_type(path: Path) -> str:
    mt, _ = mimetypes.guess_type(path.name)
    return mt or "application/octet-stream"


def _public_api_base(request: Request) -> str:
    explicit = (settings.API_PUBLIC_BASE_URL or "").strip().rstrip("/")
    if explicit:
        return explicit
    base = str(request.base_url).rstrip("/")
    prefix = settings.API_V1_PREFIX.strip().rstrip("/")
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return f"{base}{prefix}"


def build_local_play_response(*, video: Video, viewer: User, request: Request) -> VideoPlayResponse:
    rel = (video.local_video_relpath or "").strip()
    if not rel:
        raise AppError("本机成片未就绪", status_code=500, code=VIDEO_LOCAL_NOT_READY)
    path = _abs_stored_path(rel)
    if not path.is_file():
        raise AppError("本机成片文件缺失", status_code=503, code=VIDEO_LOCAL_FILE_MISSING)

    exp = int(datetime.now(timezone.utc).timestamp()) + int(settings.LOCAL_VIDEO_PLAY_TOKEN_SECONDS)
    secret = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    token = sign_local_stream_token(video_id=video.id, user_id=viewer.id, exp_unix=exp, secret=secret)
    from urllib.parse import quote

    api_base = _public_api_base(request)
    stream_url = f"{api_base}/videos/{video.id}/local-stream?token={quote(token, safe='')}"
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=int(settings.LOCAL_VIDEO_PLAY_TOKEN_SECONDS))
    return VideoPlayResponse(
        video_id=video.id,
        playback_mode="local",
        vod_video_id=None,
        play_auth=None,
        stream_url=stream_url,
        expire_time=expire_at,
        request_id=None,
    )


def _assert_author_or_admin(video: Video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id != actor.id:
        raise AppError("仅作者或管理员可上传本机成片", status_code=403, code=VIDEO_LOCAL_UPLOAD_FORBIDDEN)


def _normalize_suffix(suffix: str) -> str:
    s = (suffix or "").strip().lower()
    if not s:
        return ""
    return s if s.startswith(".") else f".{s}"


def _persist_local_file_metadata(
    db: Session,
    *,
    v: Video,
    video_id: uuid.UUID,
    dest_name: str,
    dest: Path,
    source_file_display: str,
) -> Video:
    old_rel = (v.local_video_relpath or "").strip()
    if old_rel and old_rel != dest_name:
        try:
            old_path = _abs_stored_path(old_rel)
            if old_path.is_file() and old_path != dest:
                old_path.unlink()
        except AppError:
            pass

    v.local_video_relpath = dest_name
    v.source_file_name = source_file_display[:512] or dest_name
    v.upload_status = VodUploadStatus.UPLOADED
    v.transcode_status = VodTranscodeStatus.COMPLETED
    v.updated_at = datetime.now(timezone.utc)
    db.commit()
    out = video_repository.get_by_id(db, video_id, load_tags=True)
    assert out is not None
    return out


async def save_upload_replace_local_file(
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

    suffix = Path(upload.filename or "").suffix.lower()
    allowed = _allowed_suffixes()
    if suffix not in allowed:
        raise AppError(
            f"不支持的扩展名：{suffix or '（空）'}；允许：{', '.join(sorted(allowed))}",
            status_code=400,
            code=VIDEO_LOCAL_BAD_EXTENSION,
        )

    dest_name = f"{video_id}{suffix}"
    dest = _storage_root() / dest_name
    max_bytes = int(settings.MAX_VIDEO_SIZE_MB) * 1024 * 1024

    tmp = dest.with_suffix(dest.suffix + ".part")
    total = 0
    try:
        with tmp.open("wb", buffering=_READ_WRITE_CHUNK_BYTES) as out:
            while True:
                chunk = await upload.read(_READ_WRITE_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        f"文件超过上限 {settings.MAX_VIDEO_SIZE_MB} MB",
                        status_code=413,
                        code=VIDEO_LOCAL_TOO_LARGE,
                    )
                out.write(chunk)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    display = Path(upload.filename or "").name or dest_name
    return _persist_local_file_metadata(db, v=v, video_id=video_id, dest_name=dest_name, dest=dest, source_file_display=display)


async def save_raw_body_replace_local_file(
    db: Session,
    *,
    actor: User,
    video_id: uuid.UUID,
    request: Request,
    suffix: str,
    source_file_name: str | None,
) -> Video:
    """将 **原始请求体**（非 multipart）流式写入成片目录，避免 Starlette 先落临时文件再整份拷贝。

    客户端应使用 ``Content-Type: application/octet-stream``（或 ``video/*``），勿对本 URL 使用 ``multipart/form-data``。
    """
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not video_service.can_view_video(v, actor):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)

    norm = _normalize_suffix(suffix)
    allowed = _allowed_suffixes()
    if norm not in allowed:
        raise AppError(
            f"不支持的扩展名：{norm or '（空）'}；允许：{', '.join(sorted(allowed))}",
            status_code=400,
            code=VIDEO_LOCAL_BAD_EXTENSION,
        )

    dest_name = f"{video_id}{norm}"
    dest = _storage_root() / dest_name
    max_bytes = int(settings.MAX_VIDEO_SIZE_MB) * 1024 * 1024

    tmp = dest.with_suffix(dest.suffix + ".part")
    total = 0
    try:
        with tmp.open("wb", buffering=_READ_WRITE_CHUNK_BYTES) as out:
            async for chunk in request.stream():
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        f"文件超过上限 {settings.MAX_VIDEO_SIZE_MB} MB",
                        status_code=413,
                        code=VIDEO_LOCAL_TOO_LARGE,
                    )
                out.write(chunk)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    display = (source_file_name or "").strip() or dest_name
    return _persist_local_file_metadata(
        db, v=v, video_id=video_id, dest_name=dest_name, dest=dest, source_file_display=display
    )


def resolve_stream_file_path(db: Session, *, token: str, path_video_id: uuid.UUID) -> tuple[Path, str]:
    secret = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    try:
        vid, uid, _exp = verify_local_stream_token(token, secret=secret)
    except ValueError as e:
        raise AppError("播放链接无效或已过期", status_code=403, code=VIDEO_LOCAL_STREAM_TOKEN_INVALID) from e
    if vid != path_video_id:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)

    from app.repositories import user_repository

    viewer = user_repository.get_by_id(db, uid)
    if viewer is None:
        raise AppError("播放链接无效或已过期", status_code=403, code=VIDEO_LOCAL_STREAM_TOKEN_INVALID)

    v = video_repository.get_by_id(db, vid, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not video_service.can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    video_service.assert_vod_play_permission(v, viewer)

    rel = (v.local_video_relpath or "").strip()
    if not rel:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    path = _abs_stored_path(rel)
    if not path.is_file():
        raise AppError("本机成片文件缺失", status_code=503, code=VIDEO_LOCAL_FILE_MISSING)
    return path, _guess_media_type(path)
