"""JWT 载荷与校验策略（iss/aud/iat 等）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, decode_access_token


def test_create_decode_roundtrip():
    uid = uuid.uuid4()
    tok = create_access_token(subject=str(uid))
    assert decode_access_token(tok) == uid


def test_access_token_default_ttl_is_15_minutes():
    uid = uuid.uuid4()
    tok = create_access_token(subject=str(uid))
    payload = jwt.decode(
        tok,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=[ALGORITHM],
        audience=settings.APP_NAME.strip(),
        issuer=settings.APP_NAME.strip(),
    )
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_decode_rejects_token_without_aud():
    realm = settings.APP_NAME.strip()
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": realm,
    }
    token = jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_decode_rejects_blank_token():
    assert decode_access_token("") is None
    assert decode_access_token("   \n") is None
