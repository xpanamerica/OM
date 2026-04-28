"""评论发帖滑动窗口限流（进程内；全量 conftest 关闭 Redis 路径）。"""

from unittest.mock import MagicMock

import pytest

from app.core.comment_rate_limit import (
    CommentRateLimitBackendError,
    consume_comment_post_slot,
    reset_comment_rate_limit_state,
    retry_after_seconds_for_comment_rate_limit,
)
from app.core.config import settings


def test_comment_rate_limit_third_blocked_within_window():
    reset_comment_rate_limit_state()
    k = "user:video"
    assert consume_comment_post_slot(k, max_per_minute=2)[0] is True
    assert consume_comment_post_slot(k, max_per_minute=2)[0] is True
    ok, ra = consume_comment_post_slot(k, max_per_minute=2)
    assert ok is False
    assert ra is not None and ra >= 1


def test_comment_rate_limit_zero_disables():
    reset_comment_rate_limit_state()
    k = "a:b"
    for _ in range(50):
        assert consume_comment_post_slot(k, max_per_minute=0)[0] is True


def test_retry_after_when_full_is_positive():
    reset_comment_rate_limit_state()
    k = "u:v"
    assert consume_comment_post_slot(k, max_per_minute=1) == (True, None)
    ok, ra = consume_comment_post_slot(k, max_per_minute=1)
    assert ok is False and ra is not None and ra >= 1
    ra2 = retry_after_seconds_for_comment_rate_limit(k, max_per_minute=1)
    assert ra2 is not None and ra2 >= 1


def test_consume_strict_raises_backend_error_when_redis_fails(monkeypatch):
    reset_comment_rate_limit_state()
    monkeypatch.setattr(
        "app.core.comment_rate_limit.settings",
        settings.model_copy(
            update={
                "COMMENT_RATE_LIMIT_USE_REDIS": True,
                "COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY": False,
            }
        ),
    )
    monkeypatch.setattr("app.core.comment_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr("app.core.comment_rate_limit.get_redis", lambda: m)
    with pytest.raises(CommentRateLimitBackendError):
        consume_comment_post_slot("strict-bucket", max_per_minute=2)


def test_consume_redis_path_calls_eval(monkeypatch):
    reset_comment_rate_limit_state()
    monkeypatch.setattr(
        "app.core.comment_rate_limit.settings",
        settings.model_copy(update={"COMMENT_RATE_LIMIT_USE_REDIS": True}),
    )
    monkeypatch.setattr("app.core.comment_rate_limit.redis_available_cached", lambda: True)
    m = MagicMock()
    m.eval.return_value = [1, 0]
    monkeypatch.setattr("app.core.comment_rate_limit.get_redis", lambda: m)
    ok, ra = consume_comment_post_slot("redis-bucket-1", max_per_minute=3)
    assert ok and ra is None
    m.eval.assert_called_once()
    m.eval.return_value = [0, 42]
    ok2, ra2 = consume_comment_post_slot("redis-bucket-2", max_per_minute=2)
    assert ok2 is False and ra2 == 42
