"""进程内登录尝试限流（按 IP，滑动 60 秒窗口）。

多 worker 部署时每个进程独立计数；需全局限流可后续换 Redis。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_lock = Lock()
_timestamps: dict[str, deque[float]] = defaultdict(deque)


def reset_login_rate_limit_state() -> None:
    """清空计数（供测试隔离；生产勿调用）。"""
    with _lock:
        _timestamps.clear()


def _prune_old(ip: str, now: float, window_sec: float) -> None:
    q = _timestamps[ip]
    while q and now - q[0] > window_sec:
        q.popleft()


def is_login_allowed(client_ip: str, *, max_attempts_per_minute: int) -> bool:
    """未超过上限时登记一次尝试并返回 True；超过则返回 False（不登记）。"""
    if max_attempts_per_minute <= 0:
        return True
    window = 60.0
    now = time.monotonic()
    with _lock:
        _prune_old(client_ip, now, window)
        q = _timestamps[client_ip]
        if len(q) >= max_attempts_per_minute:
            return False
        q.append(now)
        return True
