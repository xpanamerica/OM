"""评论域指标：Prometheus textformat 计数器（无第三方依赖，与 ``GET /metrics`` 配合）。

多 worker：各进程独立计数；``worker`` 标签区分进程（默认 ``pid_<pid>``），或通过 ``METRICS_INSTANCE_ID`` 注入 Pod 名等。
"""

from __future__ import annotations

import os
import threading
from typing import Final

from app.core.config import settings

_lock = threading.Lock()
_comments_created: int = 0
_comments_rate_limited: int = 0
_comments_soft_deleted: int = 0

_METRIC_HELP_TYPE: Final[list[tuple[str, str, str]]] = [
    ("app_comments_created_total", "counter", "成功持久化的评论条数。"),
    ("app_comments_post_rate_limited_total", "counter", "因发帖限流被拒绝的请求次数。"),
    ("app_comments_soft_deleted_total", "counter", "软删除评论次数。"),
]


def _worker_label_value() -> str:
    s = (settings.METRICS_INSTANCE_ID or "").strip()
    if not s:
        return f"pid_{os.getpid()}"
    return s


def _escape_label_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')[:256]


def inc_comment_created() -> None:
    global _comments_created
    with _lock:
        _comments_created += 1


def inc_comment_rate_limited() -> None:
    global _comments_rate_limited
    with _lock:
        _comments_rate_limited += 1


def inc_comment_soft_deleted() -> None:
    global _comments_soft_deleted
    with _lock:
        _comments_soft_deleted += 1


def reset_comment_metrics_for_tests() -> None:
    """仅测试：清零计数。"""
    global _comments_created, _comments_rate_limited, _comments_soft_deleted
    with _lock:
        _comments_created = 0
        _comments_rate_limited = 0
        _comments_soft_deleted = 0


def render_comment_metrics_prometheus_text() -> bytes:
    """OpenMetrics/Prometheus 兼容片段；各 counter 带 ``worker`` 标签。"""
    with _lock:
        cc, rl, sd = _comments_created, _comments_rate_limited, _comments_soft_deleted
    wq = _escape_label_value(_worker_label_value())
    worker_attr = f'worker="{wq}"'
    lines: list[str] = []
    for name, kind, desc in _METRIC_HELP_TYPE:
        lines.append(f"# HELP {name} {desc}")
        lines.append(f"# TYPE {name} {kind}")
    lines.append(f"app_comments_created_total{{{worker_attr}}} {cc}")
    lines.append(f"app_comments_post_rate_limited_total{{{worker_attr}}} {rl}")
    lines.append(f"app_comments_soft_deleted_total{{{worker_attr}}} {sd}")
    lines.append("# HELP app_comments_metrics_exposition_info 评论指标导出元信息。")
    lines.append("# TYPE app_comments_metrics_exposition_info gauge")
    lines.append(f'app_comments_metrics_exposition_info{{schema="v2",{worker_attr}}} 1')
    return ("\n".join(lines) + "\n").encode("utf-8")
