"""评论列表游标：opaque URL-safe 串，仅含 ``comment_id``（服务端再查锚点行）。"""

from __future__ import annotations

import base64
import binascii
import uuid


def encode_comment_list_cursor(*, comment_id: uuid.UUID) -> str:
    """将末条评论 id 编码为游标（避免客户端拼接时间戳与时区不一致）。"""
    raw = str(comment_id).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_comment_list_cursor(token: str) -> uuid.UUID | None:
    """解码成功返回 ``comment_id``；损坏或非法返回 ``None``。"""
    s = (token or "").strip()
    if not s:
        return None
    pad = "=" * (-len(s) % 4)
    try:
        raw = base64.urlsafe_b64decode(s + pad).decode("ascii").strip()
        return uuid.UUID(raw)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return None
