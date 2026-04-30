from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import jwt
from cryptography.fernet import Fernet, InvalidToken as FernetInvalidToken
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import security_event_repository, user_mfa_repository

MFA_CHALLENGE_CODE = "MFA_REQUIRED"
MFA_SETUP_REQUIRED_CODE = "MFA_SETUP_REQUIRED"
MFA_INVALID_CODE = "MFA_INVALID"
_MFA_CHALLENGE_AUD = "mfa-challenge"


@dataclass(frozen=True)
class MfaSetup:
    secret: str
    otpauth_uri: str


@dataclass(frozen=True)
class MfaChallenge:
    user_id: uuid.UUID
    setup_required: bool
    jti: str


def _key_bytes() -> bytes:
    return hashlib.sha256(settings.SECRET_KEY.get_secret_value().encode("utf-8")).digest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_key_bytes()))


def _keystream(nonce: bytes, size: int) -> bytes:
    out = b""
    counter = 0
    key = _key_bytes()
    while len(out) < size:
        out += hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:size]


def seal_secret(secret: str) -> str:
    return "v2:" + _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def _seal_secret_v1(secret: str) -> str:
    raw = secret.encode("utf-8")
    nonce = secrets.token_bytes(16)
    cipher = bytes(a ^ b for a, b in zip(raw, _keystream(nonce, len(raw)), strict=True))
    mac = hmac.new(_key_bytes(), nonce + cipher, hashlib.sha256).digest()
    return "v1:" + base64.urlsafe_b64encode(nonce + cipher + mac).decode("ascii")


def unseal_secret(sealed: str) -> str:
    if sealed.startswith("v2:"):
        try:
            return _fernet().decrypt(sealed[3:].encode("ascii")).decode("utf-8")
        except (FernetInvalidToken, UnicodeDecodeError) as e:
            raise ValueError("sealed secret decrypt failed") from e
    if not sealed.startswith("v1:"):
        raise ValueError("unsupported sealed secret")
    blob = base64.urlsafe_b64decode(sealed[3:].encode("ascii"))
    nonce, rest = blob[:16], blob[16:]
    cipher, mac = rest[:-32], rest[-32:]
    expected = hmac.new(_key_bytes(), nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("sealed secret MAC mismatch")
    raw = bytes(a ^ b for a, b in zip(cipher, _keystream(nonce, len(cipher)), strict=True))
    return raw.decode("utf-8")


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp(secret: str, *, for_time: int | None = None, step: int = 30, digits: int = 6) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = int((for_time if for_time is not None else time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10**digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, now: int | None = None, window: int = 1) -> bool:
    submitted = "".join(ch for ch in code.strip() if ch.isdigit())
    if len(submitted) != 6:
        return False
    current = int(time.time() if now is None else now)
    for drift in range(-window, window + 1):
        if hmac.compare_digest(_totp(secret, for_time=current + drift * 30), submitted):
            return True
    return False


def create_challenge_token(*, user_id: uuid.UUID, setup_required: bool = False) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": secrets.token_urlsafe(18),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": settings.APP_NAME.strip(),
        "aud": _MFA_CHALLENGE_AUD,
        "typ": "mfa_challenge",
        "setup_required": setup_required,
    }
    return jwt.encode(payload, settings.SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)


def decode_challenge(token: str) -> MfaChallenge | None:
    try:
        payload = jwt.decode(
            token.strip(),
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[ALGORITHM],
            audience=_MFA_CHALLENGE_AUD,
            issuer=settings.APP_NAME.strip(),
            options={"require": ["sub", "exp", "iat", "iss", "aud", "typ", "jti"]},
        )
        if payload.get("typ") != "mfa_challenge":
            return None
        return MfaChallenge(
            user_id=uuid.UUID(str(payload.get("sub"))),
            setup_required=bool(payload.get("setup_required")),
            jti=str(payload.get("jti")),
        )
    except (InvalidTokenError, ValueError, TypeError):
        return None


def decode_challenge_token(token: str) -> uuid.UUID | None:
    challenge = decode_challenge(token)
    return challenge.user_id if challenge else None


def is_mfa_enabled(db: Session, *, user_id: uuid.UUID) -> bool:
    row = user_mfa_repository.get(db, user_id=user_id)
    return bool(row and row.enabled and row.totp_secret_sealed)


def mfa_required_for_user(db: Session, user: User) -> bool:
    return user.role == UserRole.ADMIN or is_mfa_enabled(db, user_id=user.id)


def setup_required_for_user(db: Session, user: User) -> bool:
    return user.role == UserRole.ADMIN and not is_mfa_enabled(db, user_id=user.id)


def build_setup(db: Session, *, user: User) -> MfaSetup:
    secret = generate_totp_secret()
    label = quote(f"{settings.APP_NAME}:{user.email}", safe="")
    issuer = quote(settings.APP_NAME, safe="")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    user_mfa_repository.save_pending_secret(db, user_id=user.id, sealed_secret=seal_secret(secret))
    db.commit()
    return MfaSetup(secret=secret, otpauth_uri=uri)


def recovery_code_hash(code: str) -> str:
    return hashlib.sha256((settings.SECRET_KEY.get_secret_value() + ":" + code.strip()).encode()).hexdigest()


def generate_recovery_codes(count: int = 8) -> list[str]:
    return ["-".join([secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)]).upper() for _ in range(count)]


def enable_mfa(db: Session, *, user: User, code: str) -> list[str]:
    row = user_mfa_repository.get(db, user_id=user.id)
    if row is None or not row.totp_secret_sealed:
        build_setup(db, user=user)
        row = user_mfa_repository.get(db, user_id=user.id)
    assert row is not None and row.totp_secret_sealed is not None
    secret = unseal_secret(row.totp_secret_sealed)
    if not verify_totp(secret, code):
        raise ValueError(MFA_INVALID_CODE)
    recovery_codes = generate_recovery_codes()
    hashes = [recovery_code_hash(c) for c in recovery_codes]
    user_mfa_repository.enable(
        db,
        user_id=user.id,
        sealed_secret=row.totp_secret_sealed,
        recovery_code_hashes_json=json.dumps(hashes),
    )
    db.commit()
    return recovery_codes


def verify_user_mfa(db: Session, *, user: User, code: str) -> bool:
    row = user_mfa_repository.get(db, user_id=user.id)
    if row is None or not row.enabled or not row.totp_secret_sealed:
        return False
    if verify_totp(unseal_secret(row.totp_secret_sealed), code):
        return True
    hashes = json.loads(row.recovery_code_hashes_json or "[]")
    submitted = recovery_code_hash(code)
    if submitted in hashes:
        hashes.remove(submitted)
        user_mfa_repository.update_recovery_hashes(
            db, user_id=user.id, recovery_code_hashes_json=json.dumps(hashes)
        )
        db.commit()
        return True
    return False


def disable_mfa(db: Session, *, user: User) -> None:
    if user.role == UserRole.ADMIN:
        raise ValueError("ADMIN_MFA_REQUIRED")
    user_mfa_repository.disable(db, user_id=user.id)
    db.commit()


def audit_mfa_event(*, event_type: str, user: User, ip_address: str | None, detail: str | None = None) -> None:
    security_event_repository.insert_event_sync(
        event_type=event_type,
        user_id=user.id,
        ip_address=ip_address,
        subject_hash=hashlib.sha256(str(user.id).encode()).hexdigest(),
        detail=detail,
    )
