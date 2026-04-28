"""视频 HTTP 层：条件 GET（ETag）等。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Protocol


class _VideoEtagSource(Protocol):
    id: uuid.UUID
    updated_at: datetime
    row_version: int


def weak_etag_for_video(video: _VideoEtagSource, *, vod_detail_tier: str = "full") -> str:
    """弱 ETag，随 `updated_at`、`row_version` 及 VOD 绑定字段可见性分层变化。

    ``vod_detail_tier`` 须与 ``video_privacy.vod_detail_etag_tier`` 一致，否则匿名与作者可能共用
    同一 ETag 却拿到不同 JSON（304 语义错误）。
    """
    rv = getattr(video, "row_version", 0)
    raw = f"{video.id}|{video.updated_at.isoformat()}|{rv}|{vod_detail_tier}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return f'W/"{digest}"'


def if_none_match_matches(if_none_match: str | None, etag: str) -> bool:
    """解析 `If-None-Match`（支持逗号分隔多值），与当前 `etag` 精确匹配则命中。"""
    if not if_none_match or not etag:
        return False
    for part in if_none_match.split(","):
        if part.strip() == etag or part.strip() == "*":
            return True
    return False
