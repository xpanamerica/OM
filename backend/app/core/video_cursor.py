"""键集分页游标：URL-safe base64 JSON（与 taxonomy 列表风格一致）。

- **视频列表**：`encode_video_list_cursor` / `decode_video_list_cursor`，载荷 `t`+`i`（`created_at` + 视频 `id`）。
- **播放记录列表**：`encode_view_record_list_cursor` / `decode_view_record_list_cursor`，载荷同形，`t` 为 `last_viewed_at`。
- **工作流审计**：`encode_workflow_audit_cursor` / `decode_workflow_audit_cursor`，载荷 `t`+`s`（`created_at` + 全局单调 `audit_sequence`，避免 UUID 字典序与插入序不一致）。
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone


def _ensure_utc(dt: datetime) -> datetime:
    """SQLite 等驱动可能返回 naive datetime；统一为 UTC 再比较/编码。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def encode_video_list_cursor(*, created_at: datetime, row_id: uuid.UUID) -> str:
    dt = _ensure_utc(created_at)
    payload = json.dumps(
        {"t": dt.isoformat(), "i": str(row_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def encode_workflow_audit_cursor(*, created_at: datetime, audit_sequence: int) -> str:
    """工作流审计列表游标：`created_at` + 全局单调 `audit_sequence`（与 UUID 无关的稳定续页）。"""
    if audit_sequence < 1:
        raise ValueError("audit_sequence 非法")
    dt = _ensure_utc(created_at)
    payload = json.dumps(
        {"t": dt.isoformat(), "s": int(audit_sequence)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_workflow_audit_cursor(token: str) -> tuple[datetime, int]:
    if not token or not token.strip():
        raise ValueError("cursor 为空")
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    t_raw = data.get("t")
    s_raw = data.get("s")
    if not isinstance(t_raw, str) or not t_raw:
        raise ValueError("cursor 时间戳无效")
    if not isinstance(s_raw, int) or isinstance(s_raw, bool) or s_raw < 1:
        raise ValueError("cursor 序号无效")
    created_at = _ensure_utc(datetime.fromisoformat(t_raw))
    return created_at, int(s_raw)


def decode_video_list_cursor(token: str) -> tuple[datetime, uuid.UUID]:
    if not token or not token.strip():
        raise ValueError("cursor 为空")
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    t_raw = data["t"]
    row_id = uuid.UUID(data["i"])
    if not isinstance(t_raw, str) or not t_raw:
        raise ValueError("cursor 时间戳无效")
    created_at = _ensure_utc(datetime.fromisoformat(t_raw))
    return created_at, row_id


def encode_view_record_list_cursor(*, last_viewed_at: datetime, row_id: uuid.UUID) -> str:
    """播放记录列表续页：编码格式与视频列表游标相同，``t`` 表示该行 ``last_viewed_at``。"""
    return encode_video_list_cursor(created_at=last_viewed_at, row_id=row_id)


def decode_view_record_list_cursor(token: str) -> tuple[datetime, uuid.UUID]:
    """解码播放记录列表游标，得到 ``(last_viewed_at, view_record.id)``。"""
    return decode_video_list_cursor(token)
