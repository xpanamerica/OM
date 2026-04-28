"""本机视频流 URL 的短时 HMAC 令牌（``<video src>`` 无法带 Authorization）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def sign_local_stream_token(
    *,
    video_id: uuid.UUID,
    user_id: uuid.UUID,
    exp_unix: int,
    secret: bytes,
) -> str:
    payload: dict[str, Any] = {"v": str(video_id), "u": str(user_id), "exp": int(exp_unix)}
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_local_stream_token(token: str, *, secret: bytes) -> tuple[uuid.UUID, uuid.UUID, int]:
    if not token or "." not in token:
        raise ValueError("empty_or_malformed")
    body, sig = token.rsplit(".", 1)
    if not body or not sig or len(sig) != 64:
        raise ValueError("malformed")
    expect = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        raise ValueError("bad_sig")
    data = json.loads(_b64url_decode(body).decode("utf-8"))
    vid = uuid.UUID(str(data["v"]))
    uid = uuid.UUID(str(data["u"]))
    exp = int(data["exp"])
    if exp < int(time.time()):
        raise ValueError("expired")
    return vid, uid, exp
