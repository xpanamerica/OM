"""auth_rate_limit：EVALSHA 遇 NOSCRIPT 时自动 SCRIPT LOAD 重试。"""

from __future__ import annotations

import uuid

import pytest
from redis.exceptions import NoScriptError

from app.core import auth_rate_limit as arl
from app.core import config as config_module


class _FakeRedis:
    def __init__(self) -> None:
        self.script_load_calls = 0
        self.evalsha_calls = 0

    def script_load(self, _src: str) -> str:
        self.script_load_calls += 1
        return f"sha{self.script_load_calls}"

    def evalsha(self, _sha: str, numkeys: int, *parts: object):
        self.evalsha_calls += 1
        if self.evalsha_calls == 1:
            raise NoScriptError("NOSCRIPT")
        assert numkeys == 2
        assert len(parts) >= 7
        return [1, 0, 0]


def test_register_redis_path_reloads_script_on_noscript(monkeypatch):
    arl.reset_auth_rate_limit_script_shas_for_tests()
    fake = _FakeRedis()
    monkeypatch.setattr(arl, "get_redis", lambda: fake)
    monkeypatch.setattr(arl, "_use_redis", lambda: True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 50)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 500)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS", 60)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS", 3600)

    ok, ra, which = arl.try_consume_register("203.0.113.77")
    assert ok is True
    assert ra is None
    assert which is None
    assert fake.evalsha_calls == 2
    assert fake.script_load_calls == 2
