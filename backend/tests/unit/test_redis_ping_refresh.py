from __future__ import annotations

from app.infrastructure import redis as rmod


def test_ping_redis_and_refresh_cache_invokes_ping(monkeypatch):
    rmod.reset_redis_availability_cache_for_tests()
    calls = {"n": 0}

    def fake_ping() -> bool:
        calls["n"] += 1
        return True

    monkeypatch.setattr(rmod, "ping_redis", fake_ping)
    assert rmod.ping_redis_and_refresh_cache() is True
    assert calls["n"] == 1
    assert rmod.redis_available_cached() is True
