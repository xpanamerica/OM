"""播放记录域指标：进程内 Counter，与 ``GET /metrics`` 拼接导出。"""

from __future__ import annotations

import os
import threading
from typing import Final

from app.core.config import settings

_lock = threading.Lock()
_upsert_total: int = 0
_contended_insert_merge_total: int = 0

_METRIC_HELP_TYPE: Final[list[tuple[str, str, str]]] = [
    ("app_view_record_upsert_total", "counter", "成功完成的播放记录上报次数（新建、更新或并发合并）。"),
    (
        "app_view_record_contended_insert_merge_total",
        "counter",
        "因唯一约束冲突而转为更新已有行的次数（并发首插）",
    ),
]


def _worker_label_value() -> str:
    s = (settings.METRICS_INSTANCE_ID or "").strip()
    if not s:
        return f"pid_{os.getpid()}"
    return s


def _escape_label_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')[:256]


def inc_view_record_upsert() -> None:
    global _upsert_total
    with _lock:
        _upsert_total += 1


def inc_view_record_contended_insert_merge() -> None:
    global _contended_insert_merge_total
    with _lock:
        _contended_insert_merge_total += 1


def reset_view_record_metrics_for_tests() -> None:
    global _upsert_total, _contended_insert_merge_total
    with _lock:
        _upsert_total = 0
        _contended_insert_merge_total = 0


def render_view_record_metrics_prometheus_text() -> bytes:
    with _lock:
        u, c = _upsert_total, _contended_insert_merge_total
    wq = _escape_label_value(_worker_label_value())
    worker_attr = f'worker="{wq}"'
    lines: list[str] = []
    for name, kind, desc in _METRIC_HELP_TYPE:
        lines.append(f"# HELP {name} {desc}")
        lines.append(f"# TYPE {name} {kind}")
    lines.append(f"app_view_record_upsert_total{{{worker_attr}}} {u}")
    lines.append(f"app_view_record_contended_insert_merge_total{{{worker_attr}}} {c}")
    return ("\n".join(lines) + "\n").encode("utf-8")
