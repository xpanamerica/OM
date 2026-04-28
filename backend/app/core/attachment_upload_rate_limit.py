"""稿件附件上传：按用户滑动 60s 窗口限流。

优先 **Redis ZSET**（多实例一致），不可用时按配置回退进程内 deque。
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.upload_codes import UPLOAD_ATTACHMENT_RATE_LIMITED, UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE
from app.infrastructure.redis import get_redis, redis_available_cached

logger = logging.getLogger(__name__)

RL_KEY_PREFIX = "rl:attachment:post:v1"

_lock = Lock()
_timestamps: dict[str, deque[float]] = defaultdict(deque)

_LUA_CONSUME = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local maxc = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local n = redis.call('ZCARD', key)
if n >= maxc then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  if oldest == false or #oldest < 2 then
    return {0, 60}
  end
  local oldest_ts = tonumber(oldest[2])
  local retry = window - (now - oldest_ts)
  if retry < 1 then retry = 1 end
  return {0, math.ceil(retry)}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.floor(window) + 10)
return {1, 0}
"""


def reset_attachment_upload_rate_limit_for_tests() -> None:
    with _lock:
        _timestamps.clear()


def purge_attachment_upload_rate_limit_redis_keys_for_tests() -> None:
    if not redis_available_cached():
        return
    try:
        r = get_redis()
        for k in r.scan_iter(match=f"{RL_KEY_PREFIX}:*", count=200):
            r.delete(k)
    except Exception:
        pass


def _redis_key(bucket_key: str) -> str:
    return f"{RL_KEY_PREFIX}:{bucket_key}"


def _prune_old(key: str, now: float, window_sec: float) -> None:
    q = _timestamps[key]
    while q and now - q[0] > window_sec:
        q.popleft()


def _consume_memory(bucket_key: str, max_per_minute: int, window_sec: float) -> tuple[bool, int | None]:
    now = time.monotonic()
    with _lock:
        _prune_old(bucket_key, now, window_sec)
        q = _timestamps[bucket_key]
        if len(q) >= max_per_minute:
            wait = window_sec - (now - q[0])
            return False, max(1, int(math.ceil(wait)))
        q.append(now)
        return True, None


def _consume_redis(bucket_key: str, max_per_minute: int, window_sec: float) -> tuple[bool, int | None]:
    r = get_redis()
    now = time.time()
    member = f"{now:.6f}:{uuid.uuid4().hex}"
    key = _redis_key(bucket_key)
    raw = r.eval(_LUA_CONSUME, 1, key, str(now), str(window_sec), str(max_per_minute), member)
    allowed = int(raw[0]) == 1
    retry = int(raw[1]) if not allowed else 0
    return allowed, (retry if retry >= 1 else None)


def _try_consume(bucket_key: str, *, max_per_minute: int) -> tuple[bool, int | None]:
    if max_per_minute <= 0:
        return True, None
    window = 60.0
    use_redis = settings.ATTACHMENT_POST_RATE_LIMIT_USE_REDIS and redis_available_cached()
    if use_redis:
        try:
            return _consume_redis(bucket_key, max_per_minute, window)
        except Exception as e:
            if settings.ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                logger.warning(
                    "attachment_upload_rate_limit redis failed; memory fallback: %s",
                    e,
                    exc_info=False,
                )
                return _consume_memory(bucket_key, max_per_minute, window)
            raise AppError(
                "附件上传限流服务暂不可用",
                status_code=503,
                code=UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE,
            ) from e
    return _consume_memory(bucket_key, max_per_minute, window)


def consume_attachment_post_slot_or_raise(*, user_id: uuid.UUID) -> None:
    limit = settings.ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE
    if limit <= 0:
        return
    ok, retry_after = _try_consume(str(user_id), max_per_minute=limit)
    if ok:
        return
    from app.infrastructure.observability.upload_flow_metrics import inc_attachment_post_rate_limited

    inc_attachment_post_rate_limited()
    ra = str(retry_after if retry_after is not None else 60)
    raise AppError(
        "附件上传过于频繁，请稍后再试",
        status_code=429,
        code=UPLOAD_ATTACHMENT_RATE_LIMITED,
        headers={"Retry-After": ra},
    )


def attachment_post_rate_limit_storage_label() -> str:
    if settings.ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE <= 0:
        return "disabled"
    if settings.ATTACHMENT_POST_RATE_LIMIT_USE_REDIS and redis_available_cached():
        return "redis"
    return "memory"


def attachment_post_rate_limit_operational(*, redis_connected: bool | None = None) -> bool:
    if settings.ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE <= 0:
        return True
    if not settings.ATTACHMENT_POST_RATE_LIMIT_USE_REDIS:
        return True
    if settings.ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
        return True
    if redis_connected is not None:
        return redis_connected
    from app.infrastructure.redis import ping_redis

    return ping_redis()
