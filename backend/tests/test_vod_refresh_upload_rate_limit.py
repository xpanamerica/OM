"""VOD 刷新上传凭证限流：内存路径与 Redis 路径（mock）。"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
from app.core.vod_codes import VOD_REFRESH_UPLOAD_RATE_LIMITED
from app.core.vod_refresh_upload_rate_limit import (
    consume_vod_refresh_upload_slot_or_raise,
    reset_vod_refresh_upload_rate_limit_for_tests,
)


def test_vod_refresh_memory_window_blocks_third(monkeypatch):
    reset_vod_refresh_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE": 2,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS": False,
        },
    )
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.settings", s)
    uid = uuid.uuid4()
    consume_vod_refresh_upload_slot_or_raise(user_id=uid)
    consume_vod_refresh_upload_slot_or_raise(user_id=uid)
    with pytest.raises(AppError) as ei:
        consume_vod_refresh_upload_slot_or_raise(user_id=uid)
    assert ei.value.status_code == 429
    assert ei.value.code == VOD_REFRESH_UPLOAD_RATE_LIMITED
    assert ei.value.headers.get("Retry-After") is not None


def test_vod_refresh_redis_eval_path(monkeypatch):
    reset_vod_refresh_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE": 2,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS": True,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY": True,
        },
    )
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.settings", s)
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.return_value = [1, 0]
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.get_redis", lambda: m)
    consume_vod_refresh_upload_slot_or_raise(user_id=uuid.uuid4())
    m.eval.assert_called_once()


def test_vod_refresh_strict_redis_raises_503(monkeypatch):
    reset_vod_refresh_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE": 2,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS": True,
            "VOD_REFRESH_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY": False,
        },
    )
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.settings", s)
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.side_effect = RuntimeError("redis down")
    monkeypatch.setattr("app.core.vod_refresh_upload_rate_limit.get_redis", lambda: m)
    with pytest.raises(AppError) as ei:
        consume_vod_refresh_upload_slot_or_raise(user_id=uuid.uuid4())
    assert ei.value.status_code == 503
    assert ei.value.code == UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
