"""点播刷新与附件上传：Prometheus 进程内计数（与 ``GET /metrics`` 配合）。

多 worker 各进程独立计数；``worker`` 标签同评论域（``METRICS_INSTANCE_ID`` / ``pid_*``）。
"""

from __future__ import annotations

import os
import threading
from typing import Final

from app.core.config import settings

_lock = threading.Lock()
_vod_refresh_success: int = 0
_vod_refresh_aliyun_error: int = 0
_vod_refresh_rate_limited: int = 0
_attachment_post_rate_limited: int = 0

_METRIC_HELP_TYPE: Final[list[tuple[str, str, str]]] = [
    ("app_vod_refresh_upload_success_total", "counter", "VOD RefreshUploadVideo 成功返回次数。"),
    ("app_vod_refresh_upload_aliyun_errors_total", "counter", "VOD 刷新上传凭证时阿里云调用失败次数（返回 502 前）。"),
    ("app_vod_refresh_upload_rate_limited_total", "counter", "VOD 刷新上传凭证被滑动窗口限流拒绝次数。"),
    ("app_attachment_post_rate_limited_total", "counter", "附件 POST 被滑动窗口限流拒绝次数。"),
]


def _worker_label_value() -> str:
    s = (settings.METRICS_INSTANCE_ID or "").strip()
    if not s:
        return f"pid_{os.getpid()}"
    return s


def _escape_label_value(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')[:256]


def inc_vod_refresh_upload_success() -> None:
    global _vod_refresh_success
    with _lock:
        _vod_refresh_success += 1


def inc_vod_refresh_upload_aliyun_error() -> None:
    global _vod_refresh_aliyun_error
    with _lock:
        _vod_refresh_aliyun_error += 1


def inc_vod_refresh_upload_rate_limited() -> None:
    global _vod_refresh_rate_limited
    with _lock:
        _vod_refresh_rate_limited += 1


def inc_attachment_post_rate_limited() -> None:
    global _attachment_post_rate_limited
    with _lock:
        _attachment_post_rate_limited += 1


def reset_upload_flow_metrics_for_tests() -> None:
    global _vod_refresh_success, _vod_refresh_aliyun_error, _vod_refresh_rate_limited, _attachment_post_rate_limited
    with _lock:
        _vod_refresh_success = 0
        _vod_refresh_aliyun_error = 0
        _vod_refresh_rate_limited = 0
        _attachment_post_rate_limited = 0


def render_upload_flow_metrics_prometheus_text() -> bytes:
    with _lock:
        ok, ae, vrl, arl = (
            _vod_refresh_success,
            _vod_refresh_aliyun_error,
            _vod_refresh_rate_limited,
            _attachment_post_rate_limited,
        )
    wq = _escape_label_value(_worker_label_value())
    worker_attr = f'worker="{wq}"'
    lines: list[str] = []
    for name, kind, desc in _METRIC_HELP_TYPE:
        lines.append(f"# HELP {name} {desc}")
        lines.append(f"# TYPE {name} {kind}")
    lines.append(f"app_vod_refresh_upload_success_total{{{worker_attr}}} {ok}")
    lines.append(f"app_vod_refresh_upload_aliyun_errors_total{{{worker_attr}}} {ae}")
    lines.append(f"app_vod_refresh_upload_rate_limited_total{{{worker_attr}}} {vrl}")
    lines.append(f"app_attachment_post_rate_limited_total{{{worker_attr}}} {arl}")
    lines.append("# HELP app_upload_flow_metrics_exposition_info 上传链路指标导出元信息。")
    lines.append("# TYPE app_upload_flow_metrics_exposition_info gauge")
    lines.append(f'app_upload_flow_metrics_exposition_info{{schema="v1",{worker_attr}}} 1')
    return ("\n".join(lines) + "\n").encode("utf-8")
