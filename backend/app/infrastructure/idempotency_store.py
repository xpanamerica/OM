"""写操作幂等（Idempotency-Key）：Redis 优先；可选回退进程内字典（单测/单机）。"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Literal

logger = logging.getLogger(__name__)

_TTL_SEC = 86400
_mem: dict[str, tuple[str, float]] = {}
_mem_lock = threading.Lock()
_memory_fallback_warned = False


def clear_idempotency_memory_for_tests() -> None:
    """仅测试：清空进程内幂等缓存并重置 Redis 探测缓存，避免用例间互相污染。"""
    global _memory_fallback_warned
    from app.infrastructure.redis import reset_redis_availability_cache_for_tests

    with _mem_lock:
        _mem.clear()
    _memory_fallback_warned = False
    reset_redis_availability_cache_for_tests()


def _idem_storage_kind() -> Literal["redis", "memory", "none"]:
    """幂等存储后端：禁止内存回退且无 Redis 时为 none（须拒绝带 Key 的请求）。"""
    from app.core.config import settings
    from app.infrastructure.redis import redis_available_cached

    if redis_available_cached():
        return "redis"
    if settings.IDEMPOTENCY_ALLOW_MEMORY_FALLBACK:
        return "memory"
    return "none"


def verify_idempotency_startup() -> None:
    """启动时校验：禁止内存回退时必须能连上 Redis。"""
    from app.core.config import settings

    if settings.IDEMPOTENCY_ALLOW_MEMORY_FALLBACK:
        return
    try:
        from app.infrastructure.redis import get_redis

        get_redis().ping()
    except Exception as e:
        raise RuntimeError(
            "IDEMPOTENCY_ALLOW_MEMORY_FALLBACK=false 但无法连接 Redis；"
            "请修复 REDIS_URL 或仅在开发/单实例环境设为 true。"
        ) from e


def _mem_get(key: str) -> str | None:
    now = time.monotonic()
    with _mem_lock:
        row = _mem.get(key)
        if not row:
            return None
        val, exp_at = row
        if exp_at < now:
            del _mem[key]
            return None
        return val


def _mem_setex(key: str, ttl: int, value: str) -> None:
    global _memory_fallback_warned
    if not _memory_fallback_warned:
        try:
            from app.core.config import settings

            env = (settings.ENVIRONMENT or "").strip().lower()
            if env in ("production", "prod", "staging"):
                logger.warning(
                    "Idempotency-Key 存储回退到进程内字典：多实例下重放语义不一致。"
                    "请确保 Redis 可用且 REDIS_URL 正确，或在生产将 IDEMPOTENCY_ALLOW_MEMORY_FALLBACK=false。"
                )
        except Exception:
            pass
        _memory_fallback_warned = True
    exp_at = time.monotonic() + ttl
    with _mem_lock:
        _mem[key] = (value, exp_at)


def _idem_get(key: str) -> str | None:
    kind = _idem_storage_kind()
    if kind == "redis":
        from app.infrastructure.redis import get_redis

        return get_redis().get(key)
    if kind == "memory":
        return _mem_get(key)
    return None


def _idem_setex(key: str, ttl: int, value: str) -> None:
    kind = _idem_storage_kind()
    if kind == "redis":
        from app.infrastructure.redis import get_redis

        get_redis().setex(key, ttl, value)
        return
    if kind == "memory":
        _mem_setex(key, ttl, value)
        return
    logger.error(
        "Idempotency-Key 写入被跳过：Redis 不可用且已禁止内存回退；"
        "客户端可能丢失重放缓存（此前 resolve 应已拦截带 Key 请求）。"
    )


def stable_json_hash(payload: dict[str, Any]) -> str:
    """与字段顺序无关的请求指纹。"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def idempotency_resolve(
    *,
    scope: str,
    actor_id: str,
    idempotency_key: str | None,
    body_fingerprint: str,
) -> tuple[
    Literal["execute", "replay", "conflict", "unavailable"],
    dict[str, Any] | None,
]:
    """返回 `(execute|replay|conflict|unavailable, replay_body)`。"""
    if not idempotency_key or not idempotency_key.strip():
        return "execute", None
    if _idem_storage_kind() == "none":
        return "unavailable", None
    key = idempotency_key.strip()
    if len(key) > 128:
        key = key[:128]
    rkey = f"idem:v1:{scope}:{actor_id}:{key}"
    raw = _idem_get(rkey)
    if raw is None:
        return "execute", None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "execute", None
    if data.get("fp") != body_fingerprint:
        return "conflict", None
    return "replay", data.get("body")


def idempotency_store(
    *,
    scope: str,
    actor_id: str,
    idempotency_key: str,
    body_fingerprint: str,
    status: int,
    body: dict[str, Any],
) -> None:
    key = idempotency_key.strip()
    if len(key) > 128:
        key = key[:128]
    rkey = f"idem:v1:{scope}:{actor_id}:{key}"
    payload = json.dumps({"fp": body_fingerprint, "status": status, "body": body}, separators=(",", ":"))
    _idem_setex(rkey, _TTL_SEC, payload)
