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
    return jwt.encode(payload, settings.SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> UUID | None:
    raw = token.strip()
    if not raw:
        return None
    realm = settings.APP_NAME.strip()
    try:
        payload = jwt.decode(
            raw,
            settings.SECRET_KEY.get_secret_value(),
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
