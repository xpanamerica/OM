"""认证限流 Prometheus 计数：渲染与递增语义。"""

from __future__ import annotations

from app.core import auth_rate_limit as arl
from app.core import config as config_module
from app.infrastructure.observability.auth_rate_limit_metrics import (
    render_auth_rate_limit_metrics_prometheus_text,
    reset_auth_rate_limit_metrics_for_tests,
)


def test_render_contains_all_kinds_and_exposition_info():
    reset_auth_rate_limit_metrics_for_tests()
    body = render_auth_rate_limit_metrics_prometheus_text().decode()
    assert "app_auth_rate_limit_exceeded_total" in body
    assert 'kind="register_per_minute"' in body
    assert 'kind="login_fail_account"' in body
    assert "app_auth_rate_limit_redis_errors_total" in body
    assert "app_auth_rate_limit_memory_fallback_total" in body
    assert "app_auth_rate_limit_metrics_exposition_info" in body


def test_try_consume_register_increments_exceeded(monkeypatch):
    reset_auth_rate_limit_metrics_for_tests()
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 1)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 100)
    arl.reset_auth_rate_limit_memory_for_tests()
    assert arl.try_consume_register("203.0.113.1")[0] is True
    ok, _, which = arl.try_consume_register("203.0.113.1")
    assert ok is False
    assert which == "register_per_minute"
    body = render_auth_rate_limit_metrics_prometheus_text().decode()
    hit = [
        ln
        for ln in body.splitlines()
        if "app_auth_rate_limit_exceeded_total" in ln and "register_per_minute" in ln and not ln.startswith("#")
    ]
    assert len(hit) == 1
    assert hit[0].rstrip().endswith(" 1")


def test_notify_login_fail_account_increments_exceeded():
    reset_auth_rate_limit_metrics_for_tests()
    arl.notify_login_fail_account_rate_limited()
    arl.notify_login_fail_account_rate_limited()
    body = render_auth_rate_limit_metrics_prometheus_text().decode()
    hit = [
        ln
        for ln in body.splitlines()
        if "app_auth_rate_limit_exceeded_total" in ln and "login_fail_account" in ln and not ln.startswith("#")
    ]
    assert len(hit) == 1
    assert hit[0].rstrip().endswith(" 2")
