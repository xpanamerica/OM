"""评论 HTTP 层：列表条件 GET（ETag）等。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime


def weak_etag_for_comment_list_page(
    *,
    video_id: uuid.UUID,
    total: int,
    max_updated_at: datetime | None,
    limit: int,
    offset: int,
    cursor_key: str,
) -> str:
    """弱 ETag：随未软删集合（总数 + 最大 ``updated_at``）及分页键变化；不嵌入正文。"""
    mu = max_updated_at.isoformat() if max_updated_at else ""
    raw = f"{video_id}|{total}|{mu}|{limit}|{offset}|{cursor_key}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return f'W/"{digest}"'
