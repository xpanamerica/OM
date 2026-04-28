"""视频列表分页：offset 与键集 cursor（与 taxonomy_list 规则一致）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.video_codes import (
    VIDEO_LIST_CURSOR_OFFSET_CONFLICT,
    VIDEO_LIST_CURSOR_WITHOUT_LIMIT,
    VIDEO_LIST_INVALID_CURSOR,
)
from app.core.video_cursor import decode_video_list_cursor


def run_video_list(
    db: Session,
    *,
    fetch_all: Callable[..., list[Any]],
    fetch_after: Callable[..., list[Any]],
    limit: int,
    offset: int,
    cursor: str | None,
) -> tuple[list[Any], bool]:
    """返回 `(items, has_more)`；`limit+1` 探测尾页。"""
    if cursor is not None:
        c = cursor.strip()
        cursor = c or None

    if cursor and offset != 0:
        raise AppError(
            "不可同时使用 cursor 与 offset",
            status_code=400,
            code=VIDEO_LIST_CURSOR_OFFSET_CONFLICT,
        )
    if cursor is not None and limit < 1:
        raise AppError(
            "使用 cursor 时必须指定正整数 limit",
            status_code=400,
            code=VIDEO_LIST_CURSOR_WITHOUT_LIMIT,
        )

    take = limit + 1
    if cursor:
        try:
            after_created_at, after_id = decode_video_list_cursor(cursor)
        except Exception:
            raise AppError("无效的 cursor", status_code=400, code=VIDEO_LIST_INVALID_CURSOR) from None
        rows = fetch_after(
            db,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=take,
        )
    else:
        rows = fetch_all(db, limit=take, offset=offset)

    has_more = len(rows) > limit
    return rows[:limit], has_more
