"""阶段 12：VOD 日上传限流 — Redis 路径（Mock Redis，不依赖本机 Redis）。"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_DAILY_QUOTA_EXCEEDED, UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE


def _rl_mod():
    import app.core.upload_rate_limit as mod

    return mod


def test_begin_vod_upload_redis_expire_on_first_incr(monkeypatch):
    """首次 INCR 返回 1 时应对键设置 EXPIRE（便于键自动回收）。"""
    mod = _rl_mod()
    uid = uuid.uuid4()
    m = MagicMock()
    m.incr.return_value = 1
    monkeypatch.setattr(mod, "get_redis", lambda: m)
    monkeypatch.setattr(mod, "redis_available_cached", lambda: True)
    monkeypatch.setattr(
        mod,
        "settings",
        settings.model_copy(
            update={
                "VIDEO_UPLOAD_MAX_PER_USER_PER_DAY": 10,
                "VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS": True,
                "VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY": True,
            }
        ),
    )

    mod.begin_vod_upload_daily_attempt(uid)

    m.incr.assert_called_once()
    key = m.incr.call_args[0][0]
    assert key.startswith("rl:upload:vod:day:v1:")
    assert str(uid) in key
    m.expire.assert_called_once_with(key, 172800)


def test_begin_vod_upload_redis_third_exceeds_limit_raises_429_and_decr(monkeypatch):
    mod = _rl_mod()
    uid = uuid.uuid4()
    m = MagicMock()
    m.incr.side_effect = [1, 2, 3]
    monkeypatch.setattr(mod, "get_redis", lambda: m)
    monkeypatch.setattr(mod, "redis_available_cached", lambda: True)
    monkeypatch.setattr(
        mod,
        "settings",
        settings.model_copy(
            update={
                "VIDEO_UPLOAD_MAX_PER_USER_PER_DAY": 2,
                "VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS": True,
                "VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY": True,
            }
        ),
    )

    mod.begin_vod_upload_daily_attempt(uid)
    mod.begin_vod_upload_daily_attempt(uid)
    with pytest.raises(AppError) as ei:
        mod.begin_vod_upload_daily_attempt(uid)
    assert ei.value.status_code == 429
    assert ei.value.code == UPLOAD_DAILY_QUOTA_EXCEEDED
    assert "Retry-After" in ei.value.headers
    assert m.incr.call_count == 3
    m.decr.assert_called()


def test_begin_vod_upload_redis_failure_strict_returns_503(monkeypatch):
    mod = _rl_mod()
    uid = uuid.uuid4()
    m = MagicMock()
    m.incr.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(mod, "get_redis", lambda: m)
    monkeypatch.setattr(mod, "redis_available_cached", lambda: True)
    monkeypatch.setattr(
        mod,
        "settings",
        settings.model_copy(
            update={
                "VIDEO_UPLOAD_MAX_PER_USER_PER_DAY": 3,
                "VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS": True,
                "VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY": False,
            }
        ),
    )

    with pytest.raises(AppError) as ei:
        mod.begin_vod_upload_daily_attempt(uid)
    assert ei.value.status_code == 503
    assert ei.value.code == UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
