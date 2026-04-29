"""认证相关端点限流：Redis 优先（SCRIPT LOAD + EVALSHA），可回退进程内滑动窗口。

配额与滑动窗口秒数均由 ``Settings`` 配置；Redis 键包含窗口长度，避免调参后与旧计数混用。
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from redis.exceptions import NoScriptError, RedisError

from app.core.config import settings
from app.infrastructure.observability.auth_rate_limit_metrics import (
    inc_auth_rate_limit_exceeded,
    inc_auth_rate_limit_memory_fallback,
    inc_auth_rate_limit_redis_errors,
)
from app.infrastructure.redis import get_redis, ping_redis_and_refresh_cache, redis_available_cached

logger = logging.getLogger(__name__)

RL_PREFIX = "rl:auth:v2"

_lock = Lock()
_stale_probe_lock = Lock()
_script_init_lock = Lock()
_last_redis_reprobe_monotonic: float = 0.0
_SCRIPT_SHAS: dict[str, str] = {}

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
    return {0, math.ceil(window)}
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
  local retry = math.ceil(w1)
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w1 - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 1}
end
if n2 >= tonumber(m2) then
  local oldest = redis.call('ZRANGE', k2, 0, 0, 'WITHSCORES')
  local retry = math.ceil(w2)
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
  local retry = math.ceil(w)
  if oldest and #oldest >= 2 and oldest[2] then
    retry = math.ceil(w - (now - tonumber(oldest[2])))
    if retry < 1 then retry = 1 end
  end
  return {0, retry, 1}
end
if n2 >= tonumber(m2) then
  local oldest = redis.call('ZRANGE', k2, 0, 0, 'WITHSCORES')
  local retry = math.ceil(w)
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


def _eval_sha_with_noscript_retry(
    r,
    *,
    cache_key: str,
    source: str,
    numkeys: int,
    keys_and_argv: list[object],
) -> object:
    """EVALSHA，遇 ``NOSCRIPT`` 时重新 ``SCRIPT LOAD`` 再执行。"""
    if len(keys_and_argv) < numkeys:
        raise ValueError("keys_and_argv 长度须 >= numkeys")
    keys = [str(x) for x in keys_and_argv[:numkeys]]
    argv = [str(x) for x in keys_and_argv[numkeys:]]
    with _script_init_lock:
        sha = _SCRIPT_SHAS.get(cache_key)
        if sha is None:
            sha = r.script_load(source)
            _SCRIPT_SHAS[cache_key] = sha
    try:
        return r.evalsha(sha, numkeys, *keys, *argv)
    except NoScriptError:
        with _script_init_lock:
            _SCRIPT_SHAS.pop(cache_key, None)
            sha = r.script_load(source)
            _SCRIPT_SHAS[cache_key] = sha
        return r.evalsha(sha, numkeys, *keys, *argv)


def _ip_bucket(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8", errors="replace")).hexdigest()[:40]


def _subject_hash(s: str) -> str:
    return hashlib.sha256(s.strip().lower().encode("utf-8")).hexdigest()


def normalize_login_identifier_for_rate_limit(identifier: str) -> str:
    """与 ``user_repository.get_by_login_identifier`` 一致的规范化，用于账号维度限流键。"""
    ident = identifier.strip()
    if not ident:
        return ""
    if "@" in ident:
        return ident.lower()
    return ident.lower()


def subject_fingerprint(s: str) -> str:
    """写入 ``security_events.subject_hash``（邮箱或已规范化的登录串）。"""
    return _subject_hash(s)


def login_account_subject_hash(login_identifier: str) -> str:
    """与账号维度限流 Redis 键一致的 SHA-256 十六进制（写入审计）。"""
    return _login_account_key(login_identifier)


def reset_auth_rate_limit_memory_for_tests() -> None:
    with _lock:
        _mem_register_min.clear()
        _mem_register_hour.clear()
        _mem_login_ip.clear()
        _mem_login_fail.clear()
        _mem_forgot_ip.clear()
        _mem_forgot_email.clear()


def reset_auth_rate_limit_redis_probe_state_for_tests() -> None:
    global _last_redis_reprobe_monotonic
    with _stale_probe_lock:
        _last_redis_reprobe_monotonic = 0.0


def reset_auth_rate_limit_script_shas_for_tests() -> None:
    """单测隔离：清空已 ``SCRIPT LOAD`` 的 SHA 缓存。"""
    with _script_init_lock:
        _SCRIPT_SHAS.clear()


def purge_auth_rate_limit_redis_keys_for_tests() -> None:
    """删除 ``rl:auth:v2:*`` 及历史 ``rl:auth:v1:*``；不依赖 ``redis_available_cached``。"""
    try:
        r = get_redis()
        for pat in (f"{RL_PREFIX}:*", "rl:auth:v1:*"):
            for k in r.scan_iter(match=pat, count=200):
                r.delete(k)
    except Exception:
        pass


def _refresh_redis_availability_after_command_error() -> None:
    try:
        ping_redis_and_refresh_cache()
    except Exception:
        pass


def _use_redis() -> bool:
    if not settings.AUTH_RATE_LIMIT_ENABLED or not settings.AUTH_RATE_LIMIT_USE_REDIS:
        return False
    if redis_available_cached():
        return True
    reprobe = int(settings.AUTH_RATE_LIMIT_REDIS_STALE_REPROBE_SECONDS or 0)
    if reprobe <= 0:
        return False
    global _last_redis_reprobe_monotonic
    with _stale_probe_lock:
        now = time.monotonic()
        if now - _last_redis_reprobe_monotonic < reprobe:
            return False
        _last_redis_reprobe_monotonic = now
    return ping_redis_and_refresh_cache()


def _login_account_key(login_identifier: str) -> str:
    return _subject_hash(normalize_login_identifier_for_rate_limit(login_identifier))


def _mem_login_fail_bucket(sub: str) -> str:
    w = int(settings.AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS)
    return f"{sub}:w{w}"


def _redis_login_fail_key(sub: str) -> str:
    w = int(settings.AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS)
    return f"{RL_PREFIX}:login:fail:w{w}:{sub}"


def _redis_login_fail_key_legacy(sub: str) -> str:
    """不含窗口的旧键；成功登录时一并删除以免残留。"""
    return f"{RL_PREFIX}:login:fail:{sub}"


def _mem_try_dual_register(ip_tok: str) -> tuple[bool, int, str | None]:
    lim_m = settings.AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE
    lim_h = settings.AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR
    w1 = float(settings.AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS)
    w2 = float(settings.AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS)
    now = time.monotonic()
    with _lock:
        q1 = _mem_register_min[ip_tok]
        q2 = _mem_register_hour[ip_tok]
        while q1 and now - q1[0] > w1:
            q1.popleft()
        while q2 and now - q2[0] > w2:
            q2.popleft()
        if len(q1) >= lim_m:
            wait = int(math.ceil(w1 - (now - q1[0])))
            inc_auth_rate_limit_exceeded("register_per_minute")
            return False, max(1, wait), "register_per_minute"
        if len(q2) >= lim_h:
            wait = int(math.ceil(w2 - (now - q2[0])))
            inc_auth_rate_limit_exceeded("register_per_hour")
            return False, max(1, wait), "register_per_hour"
        q1.append(now)
        q2.append(now)
        return True, 0, None


def try_consume_register(client_ip: str) -> tuple[bool, int | None, str | None]:
    """返回 (是否允许, retry_after 秒, 失败原因标签)。"""
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None, None
    ip_tok = _ip_bucket(client_ip)
    mw = int(settings.AUTH_RATE_LIMIT_REGISTER_MINUTE_WINDOW_SECONDS)
    hw = int(settings.AUTH_RATE_LIMIT_REGISTER_HOUR_WINDOW_SECONDS)
    if _use_redis():
        try:
            r = get_redis()
            k1 = f"{RL_PREFIX}:reg:min:w{mw}:{ip_tok}"
            k2 = f"{RL_PREFIX}:reg:hr:w{hw}:{ip_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = _eval_sha_with_noscript_retry(
                r,
                cache_key="auth_rl:lua:register_dual:v2",
                source=_LUA_REGISTER_DUAL,
                numkeys=2,
                keys_and_argv=[
                    k1,
                    k2,
                    now,
                    mw,
                    settings.AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE,
                    hw,
                    settings.AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR,
                    member,
                ],
            )
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            which = None
            if not ok and len(raw) > 2:
                tag = int(raw[2])
                which = "register_per_minute" if tag == 1 else "register_per_hour"
            if not ok and which:
                inc_auth_rate_limit_exceeded(which)
            return ok, (retry if retry >= 1 else None), which
        except RedisError as e:
            logger.warning("auth_rate_limit register redis failed: %s", e)
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
            inc_auth_rate_limit_memory_fallback()
    allowed, ra, which = _mem_try_dual_register(ip_tok)
    return allowed, (ra if ra >= 1 else None), which


def try_consume_login_ip(client_ip: str) -> tuple[bool, int | None]:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None
    lim = settings.AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE
    win = float(settings.AUTH_RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS)
    ip_tok = _ip_bucket(client_ip)
    if _use_redis():
        try:
            r = get_redis()
            wint = int(settings.AUTH_RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS)
            key = f"{RL_PREFIX}:login:ip:w{wint}:{ip_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = _eval_sha_with_noscript_retry(
                r,
                cache_key="auth_rl:lua:zset_consume:v2",
                source=_LUA_ZSET_CONSUME,
                numkeys=1,
                keys_and_argv=[key, now, wint, lim, member],
            )
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            if not ok:
                inc_auth_rate_limit_exceeded("login_ip")
            return ok, (retry if retry >= 1 else None)
        except RedisError as e:
            logger.warning("auth_rate_limit login_ip redis failed: %s", e)
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
            inc_auth_rate_limit_memory_fallback()
    now = time.monotonic()
    with _lock:
        q = _mem_login_ip[ip_tok]
        while q and now - q[0] > win:
            q.popleft()
        if len(q) >= lim:
            wait = int(math.ceil(win - (now - q[0])))
            inc_auth_rate_limit_exceeded("login_ip")
            return False, max(1, wait)
        q.append(now)
        return True, None


def login_account_failure_count(login_identifier: str) -> int:
    """当前滑动窗口内已记录的失败次数（不含本次）。"""
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return 0
    sub = _login_account_key(login_identifier)
    win = settings.AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS
    if _use_redis():
        try:
            r = get_redis()
            key = _redis_login_fail_key(sub)
            now = time.time()
            r.zremrangebyscore(key, 0, now - win)
            return int(r.zcard(key))
        except RedisError as e:
            logger.warning("auth_rate_limit login_fail count redis failed: %s", e)
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
            inc_auth_rate_limit_memory_fallback()
    now = time.monotonic()
    bucket = _mem_login_fail_bucket(sub)
    with _lock:
        q = _mem_login_fail[bucket]
        while q and now - q[0] > win:
            q.popleft()
        return len(q)


def is_login_account_blocked(login_identifier: str) -> bool:
    return login_account_failure_count(login_identifier) >= settings.AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT


def notify_login_fail_account_rate_limited() -> None:
    """登录端在账号失败次数触顶拒绝前调用，计入 ``app_auth_rate_limit_exceeded_total{kind=...}``。"""
    inc_auth_rate_limit_exceeded("login_fail_account")


def record_login_failure(login_identifier: str) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    sub = _login_account_key(login_identifier)
    win = settings.AUTH_RATE_LIMIT_LOGIN_FAIL_WINDOW_SECONDS
    if _use_redis():
        try:
            r = get_redis()
            key = _redis_login_fail_key(sub)
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            r.zremrangebyscore(key, 0, now - win)
            r.zadd(key, {member: now})
            r.expire(key, win + 10)
        except RedisError as e:
            logger.warning("auth_rate_limit login_fail record redis failed: %s", e)
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
            inc_auth_rate_limit_memory_fallback()
        else:
            return
    now = time.monotonic()
    bucket = _mem_login_fail_bucket(sub)
    with _lock:
        q = _mem_login_fail[bucket]
        while q and now - q[0] > win:
            q.popleft()
        q.append(now)


def clear_login_failures(login_identifier: str) -> None:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return
    sub = _login_account_key(login_identifier)
    if _use_redis():
        try:
            r = get_redis()
            r.delete(_redis_login_fail_key(sub), _redis_login_fail_key_legacy(sub))
        except RedisError:
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
        return
    with _lock:
        _mem_login_fail.pop(_mem_login_fail_bucket(sub), None)
        _mem_login_fail.pop(sub, None)


def try_consume_forgot_password(client_ip: str, email_normalized: str) -> tuple[bool, int | None, str | None]:
    if not settings.AUTH_RATE_LIMIT_ENABLED:
        return True, None, None
    lim_ip = settings.AUTH_RATE_LIMIT_FORGOT_PER_IP_PER_HOUR
    lim_em = settings.AUTH_RATE_LIMIT_FORGOT_PER_EMAIL_PER_HOUR
    fw = int(settings.AUTH_RATE_LIMIT_FORGOT_WINDOW_SECONDS)
    ip_tok = _ip_bucket(client_ip)
    em_tok = _subject_hash(email_normalized)
    if _use_redis():
        try:
            r = get_redis()
            k1 = f"{RL_PREFIX}:forgot:ip:w{fw}:{ip_tok}"
            k2 = f"{RL_PREFIX}:forgot:email:w{fw}:{em_tok}"
            now = time.time()
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            raw = _eval_sha_with_noscript_retry(
                r,
                cache_key="auth_rl:lua:forgot_dual:v2",
                source=_LUA_FORGOT_DUAL,
                numkeys=2,
                keys_and_argv=[k1, k2, now, fw, lim_ip, lim_em, member],
            )
            ok = int(raw[0]) == 1
            retry = int(raw[1]) if not ok else 0
            which = None
            if not ok and len(raw) > 2:
                tag = int(raw[2])
                which = "forgot_password_per_ip" if tag == 1 else "forgot_password_per_email"
            if not ok and which:
                inc_auth_rate_limit_exceeded(which)
            return ok, (retry if retry >= 1 else None), which
        except RedisError as e:
            logger.warning("auth_rate_limit forgot redis failed: %s", e)
            inc_auth_rate_limit_redis_errors()
            _refresh_redis_availability_after_command_error()
            if not settings.AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY:
                raise
            inc_auth_rate_limit_memory_fallback()
    now = time.monotonic()
    w = float(fw)
    with _lock:
        q1 = _mem_forgot_ip[ip_tok]
        q2 = _mem_forgot_email[em_tok]
        while q1 and now - q1[0] > w:
            q1.popleft()
        while q2 and now - q2[0] > w:
            q2.popleft()
        if len(q1) >= lim_ip:
            inc_auth_rate_limit_exceeded("forgot_password_per_ip")
            return False, max(1, int(math.ceil(w - (now - q1[0])))), "forgot_password_per_ip"
        if len(q2) >= lim_em:
            inc_auth_rate_limit_exceeded("forgot_password_per_email")
            return False, max(1, int(math.ceil(w - (now - q2[0])))), "forgot_password_per_email"
        q1.append(now)
        q2.append(now)
        return True, None, None
