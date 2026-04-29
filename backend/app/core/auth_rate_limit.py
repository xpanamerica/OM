"""认证相关端点限流：Redis 优先，可回退进程内滑动窗口。

生产配额（与业务常量一致，单测可 monkeypatch 模块级常量）：
- 注册：每 IP 每分钟 3 次、每小时 10 次
- 登录：每 IP 每分钟 5 次；同一账号 15 分钟内失败最多 5 次后拒绝
- 忘记密码：每 IP 每小时 3 次；同一邮箱每小时 2 次
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from redis.exceptions import RedisError

from app.core.config import settings
from app.infrastructure.redis import get_redis, redis_available_cached

logger = logging.getLogger(__name__)

RL_PREFIX = "rl:auth:v1"

# 生产配额（测试可 monkeypatch）
REGISTER_PER_IP_PER_MINUTE = 3
REGISTER_PER_IP_PER_HOUR = 10
LOGIN_PER_IP_PER_MINUTE = 5
LOGIN_FAIL_WINDOW_SEC = 15 * 60
LOGIN_FAIL_MAX_PER_ACCOUNT = 5
FORGOT_PER_IP_PER_HOUR = 3
FORGOT_PER_EMAIL_PER_HOUR = 2

_lock = Lock()
_mem_register_min: dict[str, deque[float]] = defaultdict(deque)
_mem_register_hour: dict[str, deque[float]] = defaultdict(deque)
_mem_login_ip: dict[str, deque[float]] = defaultdict(deque)
_mem_login_fail: dict[str, deque[float]] = defaultdict(deque)
_mem_forgot_ip: dict[str, deque[float]] = defaultdict(deque)
_mem_forgot_email: dict[str, deque[float]] = defaultdict(deque)

_LUA_ZSET_CONSUME = """
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

_LUA_REGISTER_DUAL = """
local k1 = KEYS[1]
local k2 = KEYS[2]
local now = tonumber(ARGV[1])
local w1 = tonumber(ARGV[2])
local m1 = tonumber(ARGV[3])
local w2 = tonumber(ARGV[4])
local m2 = tonumber(ARGV[5])
local member = ARGV[6]
redis.call('ZREMRANGEBYSCORE', k1, 0, now - w1)
redis.call('ZREMRANGEBYSCORE', k2, 0, now - w2)
local n1 = redis.call('ZCARD', k1)
local n2 = redis.call('ZCARD', k2)
if n1 >= tonumber(m1) then
  local oldest = redis.call('ZRANGE', k1, 0, 0, 'WITHSCORES')
  local retry = 60
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w1 - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 1}
end
if n2 >= tonumber(m2) then
  local oldest = redis.call('ZRANGE', k2, 0, 0, 'WITHSCORES')
  local retry = 3600
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w2 - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 2}
end
redis.call('ZADD', k1, now, member)
redis.call('ZADD', k2, now, member)
redis.call('EXPIRE', k1, math.floor(w1) + 10)
redis.call('EXPIRE', k2, math.floor(w2) + 10)
return {1, 0, 0}
"""

_LUA_FORGOT_DUAL = """
local k1 = KEYS[1]
local k2 = KEYS[2]
local now = tonumber(ARGV[1])
local w = tonumber(ARGV[2])
local m1 = tonumber(ARGV[3])
local m2 = tonumber(ARGV[4])
local member = ARGV[5]
redis.call('ZREMRANGEBYSCORE', k1, 0, now - w)
redis.call('ZREMRANGEBYSCORE', k2, 0, now - w)
local n1 = redis.call('ZCARD', k1)
local n2 = redis.call('ZCARD', k2)
if n1 >= tonumber(m1) then
  local oldest = redis.call('ZRANGE', k1, 0, 0, 'WITHSCORES')
  local retry = 600
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 1}
end
if n2 >= tonumber(m2) then
  local oldest = redis.call('ZRANGE', k2, 0, 0, 'WITHSCORES')
  local retry = 600
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 2}
end
redis.call('ZADD', k1, now, member)
redis.call('ZADD', k2, now, member)
redis.call('EXPIRE', k1, math.floor(w) + 10)
redis.call('EXPIRE', k2, math.floor(w) + 10)
return {1, 0, 0}
"""


def _ip_bucket(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8", errors="replace")).hexdigest()[:40]


def _subject_hash(s: str) -> str:
    return hashlib.sha256(s.strip().lower().encode("utf-8")).hexdigest()


def subject_fingerprint(s: str) -> str:
    """登录标识或邮箱规范化后的指纹（写入 security_events.subject_hash）。"""
    return _subject_hash(s)


def reset_auth_rate_limit_memory_for_tests() -> None:
    with _lock:
        _mem_register_min.clear()
        _mem_register_hour.clear()
        _mem_login_ip.clear()
        _mem_login_fail.clear()
        _mem_forgot_ip.clear()
        _mem_forgot_email.clear()


def purge_auth_rate_limit_redis_keys_for_tests() -> None:
    if not redis_available_cached():
        return
    try:
        r = get_redis()
        for k in r.scan_iter(match=f"{RL_PREFIX}:*", count=200):
            r.delete(k)
    except Exception:
        pass


def _use_redis() -> bool:
    return (
        bool(settings.AUTH_RATE_LIMIT_ENABLED)
        and settings.AUTH_RATE_LIMIT_USE_REDIS
        and redis_available_cached()
    )


def _mem_try_dual_register(ip_tok: str) -> tuple[bool, int, str | None]:
    now = time.monotonic()
    w1, w2 = 60.0, 3600.0
    with _lock:
        q1 = _mem_register_min[ip_tok]
        q2 = _mem_register_hour[ip_tok]
        while q1 and now - q1[0] > w1:
            q1.popleft()
        while q2 and now - q2[0] > w2:
            q2.popleft()
        if len(q1) >= REGISTER_PER_IP_PER_MINUTE:
            wait = int(math.ceil(w1 - (now - q1[0])))
            return False, max(1, wait), "register_per_minute"
        if len(q2) >= REGISTER_PER_IP_PER_HOUR:
            wait = int(math.ceil(w2 - (now - q2[0])))
            return False, max(1, wait), "register_per_hour"
        q1.append(now)
        q2.append(now)
        return True, 0, None


def try_consume_register(client_ip: str) -> tuple[bool, int | None, str | None]:
    """返回 (是否允许, retry_after 秒, 失败原因标签)。"""
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None, None
    ip_tok = _ip_bucket(client_ip)
    if _use_redis():
        try:
            r = get_redis()
            k1 = f"{RL_PREFIX}:reg:1m:{ip_tok}"
            k2 = f"{RL_PREFIX}:reg:1h:{ip_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = r.eval(
                _LUA_REGISTER_DUAL,
                2,
                k1,
                k2,
                str(now),
                "60",
                str(REGISTER_PER_IP_PER_MINUTE),
                "3600",
                str(REGISTER_PER_IP_PER_HOUR),
                member,
            )
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            which = None
            if not ok and len(raw) > 2:
                tag = int(raw[2])
                which = "register_per_minute" if tag == 1 else "register_per_hour"
            return ok, (retry if retry >= 1 else None), which
        except RedisError as e:
            logger.warning("auth_rate_limit register redis failed: %s", e)
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
    allowed, ra, which = _mem_try_dual_register(ip_tok)
    return allowed, (ra if ra >= 1 else None), which


def try_consume_login_ip(client_ip: str) -> tuple[bool, int | None]:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None
    ip_tok = _ip_bucket(client_ip)
    if _use_redis():
        try:
            r = get_redis()
            key = f"{RL_PREFIX}:login:ip:60:{ip_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = r.eval(_LUA_ZSET_CONSUME, 1, key, str(now), "60", str(LOGIN_PER_IP_PER_MINUTE), member)
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            return ok, (retry if retry >= 1 else None)
        except RedisError as e:
            logger.warning("auth_rate_limit login_ip redis failed: %s", e)
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
    now = time.monotonic()
    with _lock:
        q = _mem_login_ip[ip_tok]
        while q and now - q[0] > 60.0:
            q.popleft()
        if len(q) >= LOGIN_PER_IP_PER_MINUTE:
            wait = int(math.ceil(60.0 - (now - q[0])))
            return False, max(1, wait)
        q.append(now)
        return True, None


def login_account_failure_count(login_identifier: str) -> int:
    """当前滑动窗口内已记录的失败次数（不含本次）。"""
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return 0
    sub = _subject_hash(login_identifier)
    if _use_redis():
        try:
            r = get_redis()
            key = f"{RL_PREFIX}:login:fail:{sub}"
            now = time.time()
            r.zremrangebyscore(key, 0, now - LOGIN_FAIL_WINDOW_SEC)
            return int(r.zcard(key))
        except RedisError as e:
            logger.warning("auth_rate_limit login_fail count redis failed: %s", e)
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
    now = time.monotonic()
    with _lock:
        q = _mem_login_fail[sub]
        while q and now - q[0] > LOGIN_FAIL_WINDOW_SEC:
            q.popleft()
        return len(q)


def is_login_account_blocked(login_identifier: str) -> bool:
    return login_account_failure_count(login_identifier) >= LOGIN_FAIL_MAX_PER_ACCOUNT


def record_login_failure(login_identifier: str) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    sub = _subject_hash(login_identifier)
    if _use_redis():
        try:
            r = get_redis()
            key = f"{RL_PREFIX}:login:fail:{sub}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            r.zremrangebyscore(key, 0, now - LOGIN_FAIL_WINDOW_SEC)
            r.zadd(key, {member: now})
            r.expire(key, LOGIN_FAIL_WINDOW_SEC + 10)
        except RedisError as e:
            logger.warning("auth_rate_limit login_fail record redis failed: %s", e)
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
        return
    now = time.monotonic()
    with _lock:
        q = _mem_login_fail[sub]
        while q and now - q[0] > LOGIN_FAIL_WINDOW_SEC:
            q.popleft()
        q.append(now)


def clear_login_failures(login_identifier: str) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    sub = _subject_hash(login_identifier)
    if _use_redis():
        try:
            r = get_redis()
            r.delete(f"{RL_PREFIX}:login:fail:{sub}")
        except RedisError:
            pass
        return
    with _lock:
        _mem_login_fail.pop(sub, None)


def try_consume_forgot_password(client_ip: str, email_normalized: str) -> tuple[bool, int | None, str | None]:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None, None
    ip_tok = _ip_bucket(client_ip)
    em_tok = _subject_hash(email_normalized)
    if _use_redis():
        try:
            r = get_redis()
            k1 = f"{RL_PREFIX}:forgot:ip:3600:{ip_tok}"
            k2 = f"{RL_PREFIX}:forgot:email:3600:{em_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = r.eval(
                _LUA_FORGOT_DUAL,
                2,
                k1,
                k2,
                str(now),
                "3600",
                str(FORGOT_PER_IP_PER_HOUR),
                str(FORGOT_PER_EMAIL_PER_HOUR),
                member,
            )
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            which = None
            if not ok and len(raw) > 2:
                tag = int(raw[2])
                which = "forgot_password_per_ip" if tag == 1 else "forgot_password_per_email"
            return ok, (retry if retry >= 1 else None), which
        except RedisError as e:
            logger.warning("auth_rate_limit forgot redis failed: %s", e)
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
    now = time.monotonic()
    w = 3600.0
    with _lock:
        q1 = _mem_forgot_ip[ip_tok]
        q2 = _mem_forgot_email[em_tok]
        while q1 and now - q1[0] > w:
            q1.popleft()
        while q2 and now - q2[0] > w:
            q2.popleft()
        if len(q1) >= FORGOT_PER_IP_PER_HOUR:
            return False, max(1, int(math.ceil(w - (now - q1[0])))), "forgot_password_per_ip"
        if len(q2) >= FORGOT_PER_EMAIL_PER_HOUR:
            return False, max(1, int(math.ceil(w - (now - q2[0])))), "forgot_password_per_email"
        q1.append(now)
        q2.append(now)
        return True, None, None
