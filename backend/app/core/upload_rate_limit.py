"""阶段 12：普通用户 VOD 上传凭证 — 按 UTC 自然日的 Redis / 内存计数限流。"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_DAILY_QUOTA_EXCEEDED, UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
from app.infrastructure.redis import get_redis, redis_available_cached

logger = logging.getLogger(__name__)

RL_KEY_PREFIX = "rl:upload:vod:day:v1"

_lock = Lock()
_memory_counts: dict[str, int] = defaultdict(int)


def reset_video_upload_rate_limit_state_for_tests() -> None:
    with _lock:
        _memory_counts.clear()


def purge_video_upload_rate_limit_redis_keys_for_tests() -> None:
    if not redis_available_cached():
        return
    try:
        r = get_redis()
        for k in r.scan_iter(match=f"{RL_KEY_PREFIX}:*", count=200):
            r.delete(k)
    except Exception:
        pass


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _memory_key(user_id: uuid.UUID) -> str:
    return f"{user_id}:{_utc_day()}"


def _redis_key(user_id: uuid.UUID) -> str:
    return f"{RL_KEY_PREFIX}:{user_id}:{_utc_day()}"


def _seconds_until_next_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def _incr_redis(user_id: uuid.UUID) -> int:
    r = get_redis()
    key = _redis_key(user_id)
    n = int(r.incr(key))
    if n == 1:
        r.expire(key, 172800)
    return n


def _decr_redis(user_id: uuid.UUID) -> None:
    try:
        r = get_redis()
        key = _redis_key(user_id)
        v = int(r.get(key) or 0)
        if v <= 0:
            return
        r.decr(key)
    except Exception:
        pass


def begin_vod_upload_daily_attempt(user_id: uuid.UUID) -> None:
    """为一次「即将请求阿里云凭证」的尝试占位；成功发凭证后勿回滚；阿里云失败须调用 ``abort_vod_upload_daily_attempt``。"""
    limit = settings.VIDEO_UPLOAD_MAX_PER_USER_PER_DAY
    if limit <= 0:
        return

    use_redis = settings.VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS and redis_available_cached()
    if use_redis:
        try:
            n = _incr_redis(user_id)
        except Exception as e:
            if settings.VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                logger.warning("upload daily limit redis failed; memory fallback: %s", e)
                with _lock:
                    mk = _memory_key(user_id)
                    _memory_counts[mk] += 1
                    n = _memory_counts[mk]
            else:
                raise AppError(
                    "上传次数限制服务暂不可用",
                    status_code=503,
                    code=UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE,
                ) from e
    else:
        with _lock:
            mk = _memory_key(user_id)
            _memory_counts[mk] += 1
            n = _memory_counts[mk]

    if n > limit:
        abort_vod_upload_daily_attempt(user_id)
        ra = str(_seconds_until_next_utc_midnight())
        raise AppError(
            f"今日上传次数已达上限（{limit} 次），请明日再试",
            status_code=429,
            code=UPLOAD_DAILY_QUOTA_EXCEEDED,
            headers={"Retry-After": ra},
        )


def abort_vod_upload_daily_attempt(user_id: uuid.UUID) -> None:
    limit = settings.VIDEO_UPLOAD_MAX_PER_USER_PER_DAY
    if limit <= 0:
        return

    use_redis = settings.VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS and redis_available_cached()
    if use_redis:
        try:
            _decr_redis(user_id)
        except Exception as e:
            if settings.VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                logger.warning("upload daily limit redis decr failed; memory fallback: %s", e)
                with _lock:
                    mk = _memory_key(user_id)
                    if _memory_counts[mk] > 0:
                        _memory_counts[mk] -= 1
            else:
                logger.warning("upload daily limit redis decr failed (strict): %s", e)
    else:
        with _lock:
            mk = _memory_key(user_id)
            if _memory_counts[mk] > 0:
                _memory_counts[mk] -= 1
