"""可选：真 Redis + EVALSHA 路径（本地或 CI 需 Redis 且显式打开开关）。

运行示例::

  RUN_AUTH_RATE_LIMIT_REDIS=1 pytest tests/integration/test_auth_rate_limit_redis.py -q
"""

from __future__ import annotations

import os

import pytest

from app.core import auth_rate_limit as arl
from app.core import config as config_module


def _redis_up() -> bool:
    try:
        from app.infrastructure.redis import get_redis

        return bool(get_redis().ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AUTH_RATE_LIMIT_REDIS", "").lower() not in ("1", "true", "yes") or not _redis_up(),
    reason="Set RUN_AUTH_RATE_LIMIT_REDIS=1 and ensure Redis is reachable (REDIS_URL).",
)


@pytest.fixture(autouse=True)
def _redis_rl_env(monkeypatch):
    from app.infrastructure.redis import ping_redis_and_refresh_cache, reset_redis_availability_cache_for_tests

    reset_redis_availability_cache_for_tests()
    assert ping_redis_and_refresh_cache() is True
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY", True)
    arl.reset_auth_rate_limit_memory_for_tests()
    arl.reset_auth_rate_limit_script_shas_for_tests()
    arl.reset_auth_rate_limit_redis_probe_state_for_tests()
    arl.purge_auth_rate_limit_redis_keys_for_tests()
    yield
    arl.purge_auth_rate_limit_redis_keys_for_tests()
    arl.reset_auth_rate_limit_script_shas_for_tests()


def test_register_limit_via_redis_lua_sha(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 2)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 100)
    ip = "198.51.100.99"
    assert arl.try_consume_register(ip)[0] is True
    assert arl.try_consume_register(ip)[0] is True
    ok, _, which = arl.try_consume_register(ip)
    assert ok is False
    assert which == "register_per_minute"


def test_login_ip_limit_via_redis_lua_sha(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE", 2)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS", 60)
    ip = "198.51.100.100"
    assert arl.try_consume_login_ip(ip)[0] is True
    assert arl.try_consume_login_ip(ip)[0] is True
    ok, _ = arl.try_consume_login_ip(ip)
    assert ok is False
