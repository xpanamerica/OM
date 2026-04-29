"""auth_rate_limit 进程内滑动窗口（Redis 关闭时）."""

from __future__ import annotations

from app.core import auth_rate_limit as arl
from app.core.config import settings


def test_memory_register_dual_window(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(arl, "REGISTER_PER_IP_PER_MINUTE", 3)
    monkeypatch.setattr(arl, "REGISTER_PER_IP_PER_HOUR", 10)
    arl.reset_auth_rate_limit_memory_for_tests()
    ip = "203.0.113.9"
    for _ in range(3):
        ok, _, _ = arl.try_consume_register(ip)
        assert ok is True
    ok, _, which = arl.try_consume_register(ip)
    assert ok is False
    assert which == "register_per_minute"
