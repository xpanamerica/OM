"""评论发帖限流：优先 Redis ZSET 滑动 60s 窗口（多实例一致），否则进程内 deque。

键名版本前缀集中在本模块，与 ``docs/architecture.md`` 说明一致。
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from app.core.config import settings
from app.infrastructure.redis import get_redis, redis_available_cached

logger = logging.getLogger(__name__)

RL_KEY_PREFIX = "rl:comment:post:v1"


class CommentRateLimitBackendError(Exception):
    """Redis 限流执行失败且 ``COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=false`` 时抛出。"""

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


def reset_comment_rate_limit_state() -> None:
    """清空进程内计数（供测试隔离）。"""
    with _lock:
        _timestamps.clear()


def purge_comment_rate_limit_redis_keys_for_tests() -> None:
    """仅测试：删除本模块写入的限流键（不 FLUSHDB）。"""
    if not redis_available_cached():
        return
    try:
        r = get_redis()
        for k in r.scan_iter(match=f"{RL_KEY_PREFIX}:*", count=200):
            r.delete(k)
    except Exception:
        pass


def comment_rate_limit_operational(*, redis_connected: bool | None = None) -> bool:
    """严格 Redis 模式（禁止内存回退）下，当前是否具备可用的限流后端。

    若传入 ``redis_connected``（如与健康检查共用同一次 ``ping``），则不再重复探测。
    """
    if settings.COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE <= 0:
        return True
    if not settings.COMMENT_RATE_LIMIT_USE_REDIS:
        return True
    if settings.COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
        return True
    if redis_connected is not None:
        return redis_connected
    from app.infrastructure.redis import ping_redis

    return ping_redis()


def comment_rate_limit_storage_label() -> str:
    """健康检查等用：当前配置下理论后端（``disabled`` / ``redis`` / ``memory``）。"""
    if settings.COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE <= 0:
        return "disabled"
    if settings.COMMENT_RATE_LIMIT_USE_REDIS and redis_available_cached():
        return "redis"
    return "memory"


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


def consume_comment_post_slot(bucket_key: str, *, max_per_minute: int) -> tuple[bool, int | None]:
    """尝试占用一条发帖配额；成功 ``(True, None)``，拒绝 ``(False, retry_after_seconds)``。"""
    if max_per_minute <= 0:
        return True, None
    window = 60.0
    use_redis = settings.COMMENT_RATE_LIMIT_USE_REDIS and redis_available_cached()
    if use_redis:
        try:
            return _consume_redis(bucket_key, max_per_minute, window)
        except Exception as e:
            if settings.COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                logger.warning(
                    "comment_rate_limit redis failed; falling back to memory: %s",
                    e,
                    exc_info=False,
                )
                return _consume_memory(bucket_key, max_per_minute, window)
            raise CommentRateLimitBackendError(str(e)) from e
    return _consume_memory(bucket_key, max_per_minute, window)


def is_comment_post_allowed(bucket_key: str, *, max_per_minute: int) -> bool:
    ok, _ = consume_comment_post_slot(bucket_key, max_per_minute=max_per_minute)
    return ok


def retry_after_seconds_for_comment_rate_limit(
    bucket_key: str, *, max_per_minute: int, window_sec: float = 60.0
) -> int | None:
    """进程内路径已满时的 ``Retry-After`` 估算（Redis 路径请用 ``consume_comment_post_slot`` 返回值）。"""
    if max_per_minute <= 0:
        return None
    now = time.monotonic()
    with _lock:
        _prune_old(bucket_key, now, window_sec)
        q = _timestamps[bucket_key]
        if len(q) < max_per_minute:
            return None
        wait = window_sec - (now - q[0])
        return max(1, int(math.ceil(wait)))
