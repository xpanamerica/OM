import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

ALGORITHM = "HS256"

# 用户不存在时仍执行一次 bcrypt 校验，使与「密码错误」路径耗时更接近，降低简单时序侧信道风险。
BCRYPT_TIMING_DUMMY_HASH = (
    "$2b$12$3X5QokBXL5Y5W39TNKvqEuEjsCwGXbaK3cKy6WDRDEjJDco9E2hUq"
)


@dataclass(frozen=True)
class JwtSigningKey:
    secret: str
    not_after: int | None = None


def _timestamp(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _jwt_signing_keys() -> dict[str, JwtSigningKey]:
    raw = (settings.JWT_SIGNING_KEYS or "").strip()
    if not raw:
        return {settings.JWT_CURRENT_KID: JwtSigningKey(settings.SECRET_KEY.get_secret_value())}
    out: dict[str, JwtSigningKey] = {}
    if raw.startswith("{"):
        data = json.loads(raw)
        current = str(data.get("current") or settings.JWT_CURRENT_KID)
        for item in data.get("keys") or []:
            kid = str(item.get("kid") or "").strip()
            secret = str(item.get("secret") or "").strip()
            if kid and secret:
                out[kid] = JwtSigningKey(secret=secret, not_after=_timestamp(item.get("not_after")))
        if current and current != settings.JWT_CURRENT_KID and settings.JWT_CURRENT_KID not in out:
            out[settings.JWT_CURRENT_KID] = out.get(current) or JwtSigningKey(settings.SECRET_KEY.get_secret_value())
        if settings.JWT_CURRENT_KID not in out:
            out[settings.JWT_CURRENT_KID] = JwtSigningKey(settings.SECRET_KEY.get_secret_value())
        return out
    for part in raw.split(","):
        if ":" not in part:
            continue
        kid, secret = part.split(":", 1)
        kid = kid.strip()
        secret = secret.strip()
        if kid and secret:
            out[kid] = JwtSigningKey(secret=secret)
    if settings.JWT_CURRENT_KID not in out:
        out[settings.JWT_CURRENT_KID] = JwtSigningKey(settings.SECRET_KEY.get_secret_value())
    return out


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(*, subject: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(tz=UTC)
    expire = now + (
        expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    realm = settings.APP_NAME.strip()
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": realm,
        "aud": realm,
    }
    keys = _jwt_signing_keys()
    kid = settings.JWT_CURRENT_KID
    key = keys[kid]
    if key.not_after is not None and key.not_after <= int(now.timestamp()):
        raise ValueError("JWT_CURRENT_KID 已过期，拒绝继续签发新 token")
    return jwt.encode(payload, key.secret, algorithm=ALGORITHM, headers={"kid": kid})


def decode_access_token(token: str) -> UUID | None:
    raw = token.strip()
    if not raw:
        return None
    realm = settings.APP_NAME.strip()
    try:
        header = jwt.get_unverified_header(raw)
        kid = str(header.get("kid") or settings.JWT_CURRENT_KID)
        key = _jwt_signing_keys().get(kid)
        if key is None:
            return None
        now_ts = int(datetime.now(tz=UTC).timestamp())
        if key.not_after is not None and key.not_after + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60) < now_ts:
            return None
        payload = jwt.decode(
            raw,
            key.secret,
            algorithms=[ALGORITHM],
            audience=realm,
            issuer=realm,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
            leeway=0,
        )
        sub = payload.get("sub")
        if sub is None:
            return None
        return UUID(str(sub))
    except (InvalidTokenError, ValueError, TypeError):
        return None


# OAuth 2.0 Bearer（RFC 6750）：401 时提示客户端按 Bearer 重试或换证
BEARER_WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}
