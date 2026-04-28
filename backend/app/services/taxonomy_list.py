"""分类 / 标签列表分页共用逻辑（offset、键集游标、limit+1 探测）。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.taxonomy_cursor import decode_taxonomy_cursor, encode_taxonomy_cursor


def run_taxonomy_list(
    db: Session,
    *,
    fetch_all: Callable[..., list[Any]],
    fetch_after: Callable[..., list[Any]],
    limit: int | None,
    offset: int,
    cursor: str | None,
) -> tuple[list[Any], bool]:
    """返回 `(items, has_more)`；`has_more` 仅在 `limit` 非空时有意义。"""
    if cursor is not None:
        c = cursor.strip()
        cursor = c or None

    if limit is None and offset != 0:
        raise AppError("使用 offset 时必须指定 limit", status_code=400)
    if cursor and offset != 0:
        raise AppError("不可同时使用 cursor 与 offset", status_code=400)
    if cursor and limit is None:
        raise AppError("使用 cursor 时必须指定 limit", status_code=400)

    if limit is None:
        rows = fetch_all(db, limit=None, offset=0)
        return rows, False

    take = limit + 1
    if cursor:
        try:
            after_name, after_id = decode_taxonomy_cursor(cursor)
        except Exception:
            raise AppError("无效的 cursor", status_code=400) from None
        rows = fetch_after(db, after_name=after_name, after_id=after_id, limit=take)
    else:
        rows = fetch_all(db, limit=take, offset=offset)

    has_more = len(rows) > limit
    return rows[:limit], has_more


def next_cursor_token(*, name: str, row_id: uuid.UUID) -> str:
    """为响应头 `X-Next-Cursor` 生成与查询参数 `cursor` 相同的编码。"""
    return encode_taxonomy_cursor(name=name, row_id=row_id)
