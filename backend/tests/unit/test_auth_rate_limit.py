"""auth_rate_limit 进程内滑动窗口与规范化语义。"""

from __future__ import annotations

from app.core import auth_rate_limit as arl
from app.core.config import settings


def test_register_max_attempts_per_minute_overrides_minute_cap(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 100)
    monkeypatch.setattr(settings, "AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE", 5)
    arl.reset_auth_rate_limit_memory_for_tests()
    ip = "203.0.113.88"
    for _ in range(5):
        ok, _, _ = arl.try_consume_register(ip)
        assert ok is True
    ok, _, which = arl.try_consume_register(ip)
    assert ok is False
    assert which == "register_per_minute"


def test_memory_register_dual_window(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 3)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 10)
    arl.reset_auth_rate_limit_memory_for_tests()
    ip = "203.0.113.9"
    for _ in range(3):
        ok, _, _ = arl.try_consume_register(ip)
        assert ok is True
    ok, _, which = arl.try_consume_register(ip)
    assert ok is False
    assert which == "register_per_minute"


def test_login_account_subject_hash_email_case_insensitive():
    a = arl.login_account_subject_hash("  User@Example.COM  ")
    b = arl.login_account_subject_hash("user@example.com")
    assert a == b


def test_login_account_subject_hash_username_case_insensitive():
    assert arl.login_account_subject_hash("Alice") == arl.login_account_subject_hash("alice")
