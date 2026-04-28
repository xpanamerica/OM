"""上传链路 Prometheus 指标：渲染与限流计数。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.vod_refresh_upload_rate_limit import (
    consume_vod_refresh_upload_slot_or_raise,
    reset_vod_refresh_upload_rate_limit_for_tests,
)
from app.infrastructure.observability.upload_flow_metrics import (
    inc_vod_refresh_upload_success,
    render_upload_flow_metrics_prometheus_text,
    reset_upload_flow_metrics_for_tests,
)


def test_render_upload_flow_metrics_contains_counters():
    reset_upload_flow_metrics_for_tests()
    inc_vod_refresh_upload_success()
    body = render_upload_flow_metrics_prometheus_text().decode()
    assert "app_vod_refresh_upload_success_total" in body
    assert "app_vod_refresh_upload_rate_limited_total" in body
    assert "app_attachment_post_rate_limited_total" in body
    assert "app_upload_flow_metrics_exposition_info" in body
    assert 'schema="v1"' in body


def test_vod_refresh_rate_limit_increments_metric(monkeypatch):
    reset_upload_flow_metrics_for_tests()
    reset_vod_refresh_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE": 1,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS": False,
        },
    )
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.settings", s)
    uid = uuid.uuid4()
    consume_vod_refresh_upload_slot_or_raise(user_id=uid)
    with pytest.raises(AppError):
        consume_vod_refresh_upload_slot_or_raise(user_id=uid)
    body = render_upload_flow_metrics_prometheus_text().decode()
    rl_line = next(
        (ln for ln in body.splitlines() if ln.startswith("app_vod_refresh_upload_rate_limited_total{")),
        "",
    )
    assert rl_line, "missing app_vod_refresh_upload_rate_limited_total"
    assert rl_line.rsplit(" ", 1)[-1] == "1"
