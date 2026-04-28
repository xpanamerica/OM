"""附件上传限流：内存路径与 Redis 路径（mock）。"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_ATTACHMENT_RATE_LIMITED, UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
from app.core.attachment_upload_rate_limit import (
    consume_attachment_post_slot_or_raise,
    reset_attachment_upload_rate_limit_for_tests,
)


def test_attachment_memory_window_blocks_third(monkeypatch):
    reset_attachment_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE": 2,
            "ATTACHMENT_POST_RATE_LIMIT_USE_REDIS": False,
        },
    )
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.settings", s)
    uid = uuid.uuid4()
    consume_attachment_post_slot_or_raise(user_id=uid)
    consume_attachment_post_slot_or_raise(user_id=uid)
    with pytest.raises(AppError) as ei:
        consume_attachment_post_slot_or_raise(user_id=uid)
    assert ei.value.status_code == 429
    assert ei.value.code == UPLOAD_ATTACHMENT_RATE_LIMITED


def test_attachment_redis_eval_path(monkeypatch):
    reset_attachment_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE": 2,
            "ATTACHMENT_POST_RATE_LIMIT_USE_REDIS": True,
            "ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY": True,
        },
    )
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.settings", s)
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.return_value = [1, 0]
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.get_redis", lambda: m)
    consume_attachment_post_slot_or_raise(user_id=uuid.uuid4())
    m.eval.assert_called_once()


def test_attachment_strict_redis_raises_503(monkeypatch):
    reset_attachment_upload_rate_limit_for_tests()
    s = settings.model_copy(
        update={
            "ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE": 2,
            "ATTACHMENT_POST_RATE_LIMIT_USE_REDIS": True,
            "ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY": False,
        },
    )
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.settings", s)
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.side_effect = RuntimeError("redis down")
    monkeypatch.setattr("app.core.attachment_upload_rate_limit.get_redis", lambda: m)
    with pytest.raises(AppError) as ei:
        consume_attachment_post_slot_or_raise(user_id=uuid.uuid4())
    assert ei.value.status_code == 503
    assert ei.value.code == UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
