"""列表键集分页：游标编码（URL-safe，不含 padding）。"""

from __future__ import annotations

import base64
import json
import uuid


def encode_taxonomy_cursor(*, name: str, row_id: uuid.UUID) -> str:
    payload = json.dumps({"n": name, "i": str(row_id)}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_taxonomy_cursor(token: str) -> tuple[str, uuid.UUID]:
    if not token or not token.strip():
        raise ValueError("cursor 为空")
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    name = data["n"]
    row_id = uuid.UUID(data["i"])
    if not isinstance(name, str) or not name:
        raise ValueError("cursor 载荷无效")
    return name, row_id
