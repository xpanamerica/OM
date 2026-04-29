"""按 IP 限制 POST /auth/register 频率（滑动 60 秒窗口，进程内）。

与 ``login_rate_limit`` 分离键空间；多 worker 时各进程独立计数。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_lock = Lock()
_timestamps: dict[str, deque[float]] = defaultdict(deque)


def reset_register_rate_limit_state() -> None:
    """单测隔离用。"""
    with _lock:
        _timestamps.clear()


def _prune_old(ip: str, now: float, window_sec: float) -> None:
    q = _timestamps[ip]
    while q and now - q[0] > window_sec:
        q.popleft()


def is_register_allowed(client_ip: str, *, max_attempts_per_minute: int) -> bool:
    """未超上限则登记一次并返回 True；否则 False（不登记）。"""
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
