from redis import Redis

from app.core.config import settings

_redis_ping_cached: bool | None = None


def get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def redis_available_cached() -> bool:
    """进程内缓存的 Redis 可达性（与幂等、评论限流等辅助特性共用）。

    首次探测失败后，同一进程内不会自动重试，避免热路径反复连接风暴；
    测试请调用 ``reset_redis_availability_cache_for_tests``。
    """
    global _redis_ping_cached
    if _redis_ping_cached is not None:
        return _redis_ping_cached
    _redis_ping_cached = ping_redis()
    return _redis_ping_cached


def reset_redis_availability_cache_for_tests() -> None:
    global _redis_ping_cached
    _redis_ping_cached = None
