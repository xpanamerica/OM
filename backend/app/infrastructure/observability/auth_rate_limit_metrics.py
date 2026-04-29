"""认证限流：Prometheus 进程内计数（与 ``GET /metrics`` 拼接导出）。

``kind`` 标签为低基数固定集合；多 worker 各进程独立计数，``worker`` 标签同评论域。
"""

from __future__ import annotations

import os
import threading
from typing import Final

from app.core.config import settings

_lock = threading.Lock()

_EXCEEDED_KINDS: Final[tuple[str, ...]] = (
    "register_per_minute",
    "register_per_hour",
    "login_ip",
    "forgot_password_per_ip",
    "forgot_password_per_email",
    "login_fail_account",
)
_exceeded: dict[str, int] = {k: 0 for k in _EXCEEDED_KINDS}
_redis_errors: int = 0
_memory_fallback: int = 0

_METRIC_HELP_TYPE: Final[list[tuple[str, str, str]]] = [
    (
        "app_auth_rate_limit_exceeded_total",
        "counter",
        "认证相关限流拒绝次数（429 前计数维度）；``kind`` 见实现内固定集合。",
    ),
    (
        "app_auth_rate_limit_redis_errors_total",
        "counter",
        "认证限流 Redis 命令异常次数（已记录日志；可能触发内存回退）。",
    ),
    (
        "app_auth_rate_limit_memory_fallback_total",
        "counter",
        "认证限流在 Redis 异常后采用进程内回退的次数。",
    ),
]


def _worker_label_value() -> str:
    s = (settings.METRICS_INSTANCE_ID or "").strip()
    if not s:
        return f"pid_{os.getpid()}"
    return s


def _escape_label_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')[:256]


def inc_auth_rate_limit_exceeded(kind: str) -> None:
    """在即将因限流拒绝请求时调用（与 ``security_events`` 写入一致）。"""
    k = kind if kind in _exceeded else "login_ip"
    with _lock:
        _exceeded[k] += 1


def inc_auth_rate_limit_redis_errors() -> None:
    global _redis_errors
    with _lock:
        _redis_errors += 1


def inc_auth_rate_limit_memory_fallback() -> None:
    global _memory_fallback
    with _lock:
        _memory_fallback += 1


def reset_auth_rate_limit_metrics_for_tests() -> None:
    global _exceeded, _redis_errors, _memory_fallback
    with _lock:
        _exceeded = {k: 0 for k in _EXCEEDED_KINDS}
        _redis_errors = 0
        _memory_fallback = 0


def render_auth_rate_limit_metrics_prometheus_text() -> bytes:
    with _lock:
        exceeded = dict(_exceeded)
        re_cnt, mf_cnt = _redis_errors, _memory_fallback
    wq = _escape_label_value(_worker_label_value())
    worker_attr = f'worker="{wq}"'
    lines: list[str] = []
    for name, kind, desc in _METRIC_HELP_TYPE:
        lines.append(f"# HELP {name} {desc}")
        lines.append(f"# TYPE {name} {kind}")
    for k in sorted(_EXCEEDED_KINDS):
        kq = _escape_label_value(k)
        lines.append(f'app_auth_rate_limit_exceeded_total{{kind="{kq}",{worker_attr}}} {exceeded.get(k, 0)}')
    lines.append(f"app_auth_rate_limit_redis_errors_total{{{worker_attr}}} {re_cnt}")
    lines.append(f"app_auth_rate_limit_memory_fallback_total{{{worker_attr}}} {mf_cnt}")
    lines.append("# HELP app_auth_rate_limit_metrics_exposition_info 认证限流指标导出元信息。")
    lines.append("# TYPE app_auth_rate_limit_metrics_exposition_info gauge")
    lines.append(f'app_auth_rate_limit_metrics_exposition_info{{schema="v1",{worker_attr}}} 1')
    return ("\n".join(lines) + "\n").encode("utf-8")
