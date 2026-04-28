"""阶段 13 增强：``GET /search/videos`` 按客户端 IP 的进程内滑动窗口限流（与登录限流同形态）。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

import app.core.config as app_config
from app.core.exceptions import AppError
from app.core.video_codes import VIDEO_SEARCH_RATE_LIMITED

_lock = Lock()
_timestamps: dict[str, deque[float]] = defaultdict(deque)


def reset_search_rate_limit_state_for_tests() -> None:
    with _lock:
        _timestamps.clear()


def _prune_old(ip: str, now: float, window_sec: float) -> None:
    q = _timestamps[ip]
    while q and now - q[0] > window_sec:
        q.popleft()


def consume_search_slot_or_raise(client_ip: str) -> None:
    """未超限时登记一次请求；超限则 429 + ``Retry-After``。"""
    max_r = int(app_config.settings.VIDEO_SEARCH_MAX_REQUESTS_PER_MINUTE)
    if max_r <= 0:
        return
    window = 60.0
    now = time.monotonic()
    with _lock:
        _prune_old(client_ip, now, window)
        q = _timestamps[client_ip]
        if len(q) >= max_r:
            raise AppError(
                "搜索请求过于频繁，请稍后再试",
                status_code=429,
                code=VIDEO_SEARCH_RATE_LIMITED,
                headers={"Retry-After": "60"},
            )
        q.append(now)
