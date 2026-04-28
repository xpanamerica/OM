from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import UserPublic

MAX_AVATAR_BYTES = 8 * 1024 * 1024
ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _storage_dir() -> Path:
    root = Path("data/user_avatars").expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def _extension(filename: str, content_type: str | None) -> str:
    raw = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    ext = raw.rsplit(".", 1)[-1].lower().strip() if "." in raw else ""
    if ext == "jpeg":
        return "jpg"
    if ext in ALLOWED_AVATAR_EXTENSIONS:
        return ext
    if content_type == "image/png":
        return "png"
    if content_type == "image/webp":
        return "webp"
    return "jpg"


async def save_avatar(db: Session, *, actor: User, upload: UploadFile) -> UserPublic:
    content_type = (upload.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise AppError("头像仅支持 JPG、PNG、WebP 图片", status_code=400)

    ext = _extension(upload.filename or "", content_type)
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise AppError("头像仅支持 JPG、PNG、WebP 图片", status_code=400)

    root = _storage_dir()
    root.mkdir(parents=True, exist_ok=True)
    storage_name = f"{actor.id}-{uuid.uuid4().hex}.{ext}"
    dest = root / storage_name

    total = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await upload.read(512 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_AVATAR_BYTES:
                    raise AppError("头像大小不能超过 8MB", status_code=400)
                f.write(chunk)
    except AppError:
        dest.unlink(missing_ok=True)
        raise
    except OSError as e:
        dest.unlink(missing_ok=True)
        raise AppError(f"无法保存头像：{e}", status_code=500) from e

    if total == 0:
        dest.unlink(missing_ok=True)
        raise AppError("头像不能为空文件", status_code=400)

    old_url = actor.avatar_url
    actor.avatar_url = f"{settings.API_V1_PREFIX}/users/{actor.id}/avatar"
    db.add(actor)
    db.commit()
    db.refresh(actor)

    if old_url:
        for old in root.glob(f"{actor.id}-*"):
            if old.name != storage_name:
                old.unlink(missing_ok=True)

    return UserPublic.model_validate(actor)


def avatar_file_path(db: Session, *, user_id: uuid.UUID) -> tuple[Path, str]:
    user = user_repository.get_by_id(db, user_id)
    if user is None or not user.avatar_url:
        raise AppError("头像不存在", status_code=404)
    root = _storage_dir()
    matches = sorted(root.glob(f"{user_id}-*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for path in matches:
        if path.is_file():
            try:
                if path.resolve().parent != root.resolve():
                    continue
            except OSError:
                continue
            media = "image/webp" if path.suffix.lower() == ".webp" else "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            return path, media
    raise AppError("头像文件缺失", status_code=404)
