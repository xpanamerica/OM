"""阶段 12：上传前安全校验（扩展名、大小、标题/描述长度等）。"""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import (
    UPLOAD_ATTACHMENT_EXTENSION_NOT_ALLOWED,
    UPLOAD_ATTACHMENT_FILE_TOO_LARGE,
    UPLOAD_COVER_EXTENSION_NOT_ALLOWED,
    UPLOAD_DESCRIPTION_TOO_LONG,
    UPLOAD_TITLE_TOO_LONG,
    UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED,
    UPLOAD_VIDEO_FILE_TOO_LARGE,
)


def _parse_ext_csv(raw: str) -> frozenset[str]:
    return frozenset(
        p.strip().lstrip(".").lower()
        for p in raw.replace(";", ",").split(",")
        if p.strip()
    )


def allowed_video_extensions() -> frozenset[str]:
    return _parse_ext_csv(settings.ALLOWED_VIDEO_EXTENSIONS)


def allowed_cover_extensions() -> frozenset[str]:
    return _parse_ext_csv(settings.ALLOWED_COVER_EXTENSIONS)


def allowed_attachment_extensions() -> frozenset[str]:
    return _parse_ext_csv(settings.ALLOWED_ATTACHMENT_EXTENSIONS)


def filename_extension(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in base:
        return ""
    return base.rsplit(".", 1)[-1].strip().lower()


def extension_from_cover_url(cover_url: str) -> str | None:
    path = urlparse(cover_url).path
    if not path or "." not in path:
        return None
    return path.rsplit(".", 1)[-1].strip().lower()


def assert_vod_upload_payload_ok(
    *,
    title: str,
    description: str | None,
    filename: str,
    file_size: int,
    cover_url: str | None,
) -> None:
    max_title = settings.MAX_VIDEO_TITLE_LENGTH
    if len(title) > max_title:
        raise AppError(
            f"标题长度超过上限（{max_title} 字符）",
            status_code=400,
            code=UPLOAD_TITLE_TOO_LONG,
        )
    max_desc = settings.MAX_VIDEO_DESCRIPTION_LENGTH
    if max_desc == 0:
        if description:
            raise AppError("当前配置不允许填写描述", status_code=400, code=UPLOAD_DESCRIPTION_TOO_LONG)
    elif description is not None and len(description) > max_desc:
        raise AppError(
            f"描述长度超过上限（{max_desc} 字符）",
            status_code=400,
            code=UPLOAD_DESCRIPTION_TOO_LONG,
        )

    ext = filename_extension(filename)
    allowed_v = allowed_video_extensions()
    if not ext or ext not in allowed_v:
        raise AppError(
            f"视频文件扩展名不在白名单内（允许：{', '.join(sorted(allowed_v))}）",
            status_code=400,
            code=UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED,
        )

    max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise AppError(
            f"文件大小超过上限（{settings.MAX_VIDEO_SIZE_MB} MB）",
            status_code=400,
            code=UPLOAD_VIDEO_FILE_TOO_LARGE,
        )

    if cover_url:
        cext = extension_from_cover_url(cover_url)
        allowed_c = allowed_cover_extensions()
        if not cext or cext not in allowed_c:
            raise AppError(
                f"封面 URL 路径扩展名不在白名单内（允许：{', '.join(sorted(allowed_c))}）",
                status_code=400,
                code=UPLOAD_COVER_EXTENSION_NOT_ALLOWED,
            )


def assert_video_text_and_cover_ok(
    *,
    title: str,
    description: str | None,
    cover_url: str | None,
) -> None:
    max_title = settings.MAX_VIDEO_TITLE_LENGTH
    if len(title) > max_title:
        raise AppError(
            f"标题长度超过上限（{max_title} 字符）",
            status_code=400,
            code=UPLOAD_TITLE_TOO_LONG,
        )
    max_desc = settings.MAX_VIDEO_DESCRIPTION_LENGTH
    if max_desc == 0:
        if description:
            raise AppError("当前配置不允许填写描述", status_code=400, code=UPLOAD_DESCRIPTION_TOO_LONG)
    elif description is not None and len(description) > max_desc:
        raise AppError(
            f"描述长度超过上限（{max_desc} 字符）",
            status_code=400,
            code=UPLOAD_DESCRIPTION_TOO_LONG,
        )
    if cover_url:
        cext = extension_from_cover_url(cover_url)
        allowed_c = allowed_cover_extensions()
        if not cext or cext not in allowed_c:
            raise AppError(
                f"封面 URL 路径扩展名不在白名单内（允许：{', '.join(sorted(allowed_c))}）",
                status_code=400,
                code=UPLOAD_COVER_EXTENSION_NOT_ALLOWED,
            )


def assert_attachment_upload_ok(*, filename: str, declared_size: int | None) -> None:
    """校验附属文件扩展名与大小（``declared_size`` 为 None 时仅校验扩展名）。"""
    ext = filename_extension(filename)
    allowed_a = allowed_attachment_extensions()
    if not ext or ext not in allowed_a:
        raise AppError(
            f"附件扩展名不在白名单内（允许：{', '.join(sorted(allowed_a))}）",
            status_code=400,
            code=UPLOAD_ATTACHMENT_EXTENSION_NOT_ALLOWED,
        )
    if declared_size is not None:
        max_bytes = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        if declared_size > max_bytes:
            raise AppError(
                f"附件大小超过上限（{settings.MAX_ATTACHMENT_SIZE_MB} MB）",
                status_code=400,
                code=UPLOAD_ATTACHMENT_FILE_TOO_LARGE,
            )


def assert_source_file_name_extension_ok(source_file_name: str | None) -> None:
    if not source_file_name:
        return
    ext = filename_extension(source_file_name)
    allowed_v = allowed_video_extensions()
    if not ext or ext not in allowed_v:
        raise AppError(
            f"源文件名扩展名不在白名单内（允许：{', '.join(sorted(allowed_v))}）",
            status_code=400,
            code=UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED,
        )
