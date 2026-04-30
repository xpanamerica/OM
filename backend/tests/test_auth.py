from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from pydantic import SecretStr

from app.core import security
from app.core import config as config_module
from app.core.config import settings
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.security_event import SecurityEvent
from app.models.user import User
from app.models.user_auth_state import UserAuthState
from app.services import mfa_service
from app.services import turnstile_service
from tests.support.openapi_contracts import assert_openapi_paths, collect_operation_tags, openapi_skip_unless_exposed


def _csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get(settings.CSRF_COOKIE_NAME)
    assert token
    return {settings.CSRF_HEADER_NAME: token}


def test_register_login_me(client):
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "alice@example.com",
            "username": "alice",
            "password": "secret1234",
        },
    )
    assert r.status_code == 201, r.text
    assert "no-store" in (r.headers.get("cache-control") or "").lower()
    body = r.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["role"] == "user"

    r2 = client.post(
        f"{prefix}/auth/login",
        data={"username": "alice", "password": "secret1234"},
    )
    assert r2.status_code == 200, r2.text
    assert "no-store" in (r2.headers.get("cache-control") or "").lower()
    token = r2.json()["access_token"]
    assert r2.json().get("token_type") == "bearer"

    r3 = client.get(f"{prefix}/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200, r3.json()
    assert "private" in (r3.headers.get("cache-control") or "").lower()
    assert r3.json()["username"] == "alice"


def test_refresh_token_cookie_rotates_and_reuse_revokes_session(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "refresh@example.com", "username": "refreshuser", "password": "secret1234"},
    ).status_code == 201
    login = client.post(
        f"{prefix}/auth/login",
        data={"username": "refreshuser", "password": "secret1234"},
    )
    assert login.status_code == 200, login.text
    old_cookie = client.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert old_cookie

    missing_csrf = client.post(f"{prefix}/auth/refresh")
    assert missing_csrf.status_code == 401

    refreshed = client.post(f"{prefix}/auth/refresh", headers=_csrf_headers(client))
    assert refreshed.status_code == 200, refreshed.text
    assert "access_token" in refreshed.json()

    db_session.expire_all()
    rows = db_session.execute(select(RefreshToken).order_by(RefreshToken.created_at)).scalars().all()
    assert len(rows) == 2
    assert sum(1 for row in rows if row.revoked_at is None) == 1
    assert sum(1 for row in rows if row.revoked_at is not None) == 1

    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, old_cookie)
    reused = client.post(f"{prefix}/auth/refresh", headers=_csrf_headers(client))
    assert reused.status_code == 401
    db_session.expire_all()
    active = int(
        db_session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        or 0
    )
    assert active == 0


def test_logout_deletes_refresh_token(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "logout@example.com", "username": "logoutuser", "password": "secret1234"},
    ).status_code == 201
    assert client.post(
        f"{prefix}/auth/login",
        data={"username": "logoutuser", "password": "secret1234"},
    ).status_code == 200
    assert int(db_session.scalar(select(func.count()).select_from(RefreshToken)) or 0) == 1
    assert client.post(f"{prefix}/auth/logout").status_code == 401
    logged_out = client.post(f"{prefix}/auth/logout", headers=_csrf_headers(client))
    assert logged_out.status_code == 204
    db_session.expire_all()
    assert int(db_session.scalar(select(func.count()).select_from(RefreshToken)) or 0) == 0


def test_totp_mfa_login_challenge_and_recovery_code(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "mfa@example.com", "username": "mfauser", "password": "secret1234"},
    ).status_code == 201
    user = db_session.execute(select(User).where(User.username == "mfauser")).scalar_one()
    setup = mfa_service.build_setup(db_session, user=user)
    recovery_codes = mfa_service.enable_mfa(db_session, user=user, code=mfa_service._totp(setup.secret))
    assert recovery_codes

    login = client.post(f"{prefix}/auth/login", data={"username": "mfauser", "password": "secret1234"})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["mfa_required"] is True
    assert body["access_token"] is None
    challenge = body["mfa_challenge_token"]

    bad = client.post(f"{prefix}/auth/mfa/verify-login", json={"mfa_challenge_token": challenge, "code": "000000"})
    assert bad.status_code == 401

    ok = client.post(
        f"{prefix}/auth/mfa/verify-login",
        json={"mfa_challenge_token": challenge, "code": recovery_codes[0]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]

    second_use = client.post(
        f"{prefix}/auth/mfa/verify-login",
        json={"mfa_challenge_token": challenge, "code": recovery_codes[0]},
    )
    assert second_use.status_code == 401


def test_mfa_verify_login_is_rate_limited(client, db_session, monkeypatch):
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_MFA_MAX_ATTEMPTS", 2)
    reset_auth_rate_limit_memory_for_tests()

    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "mfa-limit@example.com", "username": "mfalimit", "password": "secret1234"},
    ).status_code == 201
    user = db_session.execute(select(User).where(User.username == "mfalimit")).scalar_one()
    setup = mfa_service.build_setup(db_session, user=user)
    mfa_service.enable_mfa(db_session, user=user, code=mfa_service._totp(setup.secret))

    login = client.post(f"{prefix}/auth/login", data={"username": "mfalimit", "password": "secret1234"})
    challenge = login.json()["mfa_challenge_token"]
    assert client.post(f"{prefix}/auth/mfa/verify-login", json={"mfa_challenge_token": challenge, "code": "000000"}).status_code == 401
    assert client.post(f"{prefix}/auth/mfa/verify-login", json={"mfa_challenge_token": challenge, "code": "000000"}).status_code == 401
    limited = client.post(f"{prefix}/auth/mfa/verify-login", json={"mfa_challenge_token": challenge, "code": "000000"})
    assert limited.status_code == 429


def test_admin_without_mfa_gets_setup_challenge(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "admin-mfa@example.com", "username": "adminmfa", "password": "secret1234"},
    ).status_code == 201
    db_session.execute(update(User).where(User.username == "adminmfa").values(role=UserRole.ADMIN))
    db_session.commit()

    login = client.post(f"{prefix}/auth/login", data={"username": "adminmfa", "password": "secret1234"})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["mfa_required"] is True
    assert body["mfa_setup_required"] is True
    assert body["mfa_challenge_token"]


def test_admin_dependency_rejects_old_admin_token_without_mfa(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "old-admin@example.com", "username": "oldadmin", "password": "secret1234"},
    ).status_code == 201
    user = db_session.execute(select(User).where(User.username == "oldadmin")).scalar_one()
    db_session.execute(update(User).where(User.id == user.id).values(role=UserRole.ADMIN))
    db_session.commit()
    old_token = security.create_access_token(subject=str(user.id))
    denied = client.get(f"{prefix}/admin/settings", headers={"Authorization": f"Bearer {old_token}"})
    assert denied.status_code == 403


def test_auth_sessions_list_and_revoke_other_session(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "session@example.com", "username": "sessionuser", "password": "secret1234"},
    ).status_code == 201
    login = client.post(
        f"{prefix}/auth/login",
        data={"username": "sessionuser", "password": "secret1234"},
        headers={"User-Agent": "pytest-linux"},
    )
    token = login.json()["access_token"]

    sessions = client.get(f"{prefix}/auth/sessions", headers={"Authorization": f"Bearer {token}"})
    assert sessions.status_code == 200, sessions.text
    rows = sessions.json()["sessions"]
    assert len(rows) == 1
    assert rows[0]["is_current"] is True

    revoke_others = client.post(
        f"{prefix}/auth/sessions/revoke-others",
        headers={"Authorization": f"Bearer {token}", **_csrf_headers(client)},
    )
    assert revoke_others.status_code == 200
    assert revoke_others.json()["revoked_count"] == 0


def test_jwt_kid_rotation_accepts_current_and_previous_keys(monkeypatch):
    class DummySettings:
        APP_NAME = settings.APP_NAME
        ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        SECRET_KEY = SecretStr("fallback-secret-key-that-is-long-enough-for-tests")
        JWT_CURRENT_KID = "new"
        JWT_SIGNING_KEYS = "old:old-secret-key-that-is-long-enough,new:new-secret-key-that-is-long-enough"

    monkeypatch.setattr(security, "settings", DummySettings())
    new_token = security.create_access_token(subject="00000000-0000-0000-0000-000000000001")
    assert security.decode_access_token(new_token)

    DummySettings.JWT_CURRENT_KID = "old"
    old_token = security.create_access_token(subject="00000000-0000-0000-0000-000000000002")
    DummySettings.JWT_CURRENT_KID = "new"
    assert security.decode_access_token(old_token)


def test_jwt_json_key_lifecycle_rejects_expired_old_key(monkeypatch):
    class DummySettings:
        APP_NAME = settings.APP_NAME
        ACCESS_TOKEN_EXPIRE_MINUTES = 15
        SECRET_KEY = SecretStr("fallback-secret-key-that-is-long-enough-for-tests")
        JWT_CURRENT_KID = "new"
        JWT_SIGNING_KEYS = (
            '{"keys":['
            '{"kid":"old","secret":"old-secret-key-that-is-long-enough","not_after":1},'
            '{"kid":"new","secret":"new-secret-key-that-is-long-enough"}'
            "]}"
        )

    monkeypatch.setattr(security, "settings", DummySettings())
    new_token = security.create_access_token(subject="00000000-0000-0000-0000-000000000003")
    assert security.decode_access_token(new_token)

    now = datetime.now(tz=UTC)
    old_token = security.jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000004",
            "iat": int((now - timedelta(minutes=20)).timestamp()),
            "exp": int((now + timedelta(minutes=1)).timestamp()),
            "iss": settings.APP_NAME.strip(),
            "aud": settings.APP_NAME.strip(),
        },
        "old-secret-key-that-is-long-enough",
        algorithm=security.ALGORITHM,
        headers={"kid": "old"},
    )
    assert security.decode_access_token(old_token) is None


def test_register_rejects_password_over_72_utf8_bytes(client):
    prefix = settings.API_V1_PREFIX
    # 每个「あ」占 3 字节，25*3=75 > 72
    long_pw = "あ" * 25
    r = client.post(
        f"{prefix}/auth/register",
        json={"email": "x@y.com", "username": "u1", "password": long_pw},
    )
    assert r.status_code == 422


def test_register_persists_bcrypt_not_plain_password(client, db_session):
    """库中仅存 bcrypt 串，不包含注册明文口令。"""
    prefix = settings.API_V1_PREFIX
    plain = "mySecret12"
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "hashcheck@example.com",
            "username": "hashuser",
            "password": plain,
        },
    )
    assert r.status_code == 201, r.text
    row = db_session.execute(select(User).where(User.email == "hashcheck@example.com")).scalar_one()
    hp = row.hashed_password
    assert hp.startswith("$2"), "应为 bcrypt 哈希前缀"
    assert plain not in hp
    assert row.username == "hashuser"


def test_register_strips_username_and_email(client):
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "  MixedCase@Example.COM  ",
            "username": "  stripuser  ",
            "password": "secret1234",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "mixedcase@example.com"
    assert body["username"] == "stripuser"


def test_register_requires_turnstile_token_when_bypass_disabled(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", False)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_SECRET", SecretStr("turnstile-test-secret"))
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "turnstile-missing@example.com",
            "username": "turnstilemissing",
            "password": "secret1234",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == turnstile_service.TURNSTILE_REQUIRED_CODE


def test_register_rejects_invalid_turnstile_token(client, monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": False, "error-codes": ["invalid-input-response"]}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data):
            assert data["secret"] == "turnstile-test-secret"
            assert data["response"] == "bad-token"
            return _Response()

    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", False)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_SECRET", SecretStr("turnstile-test-secret"))
    monkeypatch.setattr(turnstile_service.httpx, "Client", _Client)
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "turnstile-invalid@example.com",
            "username": "turnstileinvalid",
            "password": "secret1234",
            "turnstile_token": "bad-token",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == turnstile_service.TURNSTILE_INVALID_CODE


def test_register_rejects_turnstile_hostname_mismatch(client, monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "hostname": "evil.example", "action": "register"}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data):
            return _Response()

    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", False)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_SECRET", SecretStr("turnstile-test-secret"))
    monkeypatch.setattr(config_module.settings, "TURNSTILE_ALLOWED_HOSTNAMES", ["app.example.com"])
    monkeypatch.setattr(turnstile_service.httpx, "Client", _Client)
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "turnstile-host@example.com",
            "username": "turnstilehost",
            "password": "secret1234",
            "turnstile_token": "host-token",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == turnstile_service.TURNSTILE_HOSTNAME_INVALID_CODE


def test_register_rejects_turnstile_action_mismatch(client, monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "hostname": "app.example.com", "action": "login"}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data):
            return _Response()

    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", False)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_SECRET", SecretStr("turnstile-test-secret"))
    monkeypatch.setattr(config_module.settings, "TURNSTILE_ALLOWED_HOSTNAMES", ["app.example.com"])
    monkeypatch.setattr(turnstile_service.httpx, "Client", _Client)
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "turnstile-action@example.com",
            "username": "turnstileaction",
            "password": "secret1234",
            "turnstile_token": "action-token",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == turnstile_service.TURNSTILE_ACTION_INVALID_CODE


def test_login_requires_turnstile_after_three_failures(client, monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "hostname": "app.example.com", "action": "login"}

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data):
            assert data["response"] == "ok-token"
            return _Response()

    prefix = settings.API_V1_PREFIX
    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", True)
    monkeypatch.setattr(config_module.settings, "AUTH_REGISTRATION_REQUIRES_APPROVAL", False)
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "turnstile-login@example.com",
            "username": "turnstilelogin",
            "password": "secret1234",
        },
    )
    assert r.status_code == 201, r.text

    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE", 100)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_LOGIN_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_BYPASS", False)
    monkeypatch.setattr(config_module.settings, "TURNSTILE_SECRET", SecretStr("turnstile-test-secret"))
    monkeypatch.setattr(config_module.settings, "TURNSTILE_ALLOWED_HOSTNAMES", ["app.example.com"])
    monkeypatch.setattr(turnstile_service.httpx, "Client", _Client)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    for _ in range(3):
        bad = client.post(
            f"{prefix}/auth/login",
            data={"username": "turnstilelogin", "password": "wrongpass"},
        )
        assert bad.status_code == 401

    missing = client.post(
        f"{prefix}/auth/login",
        data={"username": "turnstilelogin", "password": "secret1234"},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == turnstile_service.TURNSTILE_REQUIRED_CODE

    ok = client.post(
        f"{prefix}/auth/login",
        data={
            "username": "turnstilelogin",
            "password": "secret1234",
            "turnstile_token": "ok-token",
        },
    )
    assert ok.status_code == 200, ok.text


def test_register_requires_admin_approval_when_enabled(client, db_session, monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_REGISTRATION_REQUIRES_APPROVAL", True)
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "pending@example.com",
            "username": "pendinguser",
            "password": "secret1234",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_active"] is False

    denied = client.post(
        f"{prefix}/auth/login",
        data={"username": "pendinguser", "password": "secret1234"},
    )
    assert denied.status_code == 401

    row = db_session.execute(select(User).where(User.email == "pending@example.com")).scalar_one()
    row.is_active = True
    db_session.add(row)
    db_session.commit()

    approved = client.post(
        f"{prefix}/auth/login",
        data={"username": "pendinguser", "password": "secret1234"},
    )
    assert approved.status_code == 200, approved.text
    assert "access_token" in approved.json()


def test_email_normalized_on_register(client):
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/register",
        json={
            "email": "MixedCase@Example.COM",
            "username": "mixuser",
            "password": "secret1234",
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == "mixedcase@example.com"


def test_login_returns_429_after_rate_limit_threshold(client, monkeypatch):
    """限流开启时，同一客户端 IP 超限 POST /auth/login 须 429 且 JSON 体符合约定。"""
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE", 2)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    for _ in range(2):
        r = client.post(
            f"{prefix}/auth/login",
            data={"username": "nobody", "password": "wrongpass12"},
        )
        assert r.status_code == 401
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "nobody", "password": "wrongpass12"},
    )
    assert r.status_code == 429
    j = r.json()
    assert j.get("success") is False
    assert j.get("message")
    assert r.headers.get("Retry-After") or r.headers.get("retry-after")


def test_login_account_failures_merge_username_case(client, monkeypatch):
    """用户名大小写不敏感：失败计数应落在同一桶。"""
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT", 2)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    assert (
        client.post(
            f"{prefix}/auth/login",
            data={"username": "CaseUser", "password": "wrong"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{prefix}/auth/login",
            data={"username": "caseuser", "password": "wrong"},
        ).status_code
        == 401
    )
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "CASEUSER", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json().get("detail") == "用户名或密码错误"


def test_login_account_blocked_after_repeated_failures(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT", 2)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    for _ in range(2):
        assert client.post(
            f"{prefix}/auth/login",
            data={"username": "nobody", "password": "wrong"},
        ).status_code == 401
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "nobody", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json().get("detail") == "用户名或密码错误"


def test_existing_user_db_lockout_persists_and_clears_on_success(client, db_session, monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE", 100)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_FAIL_MAX_PER_ACCOUNT", 2)
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "lock@example.com", "username": "lockuser", "password": "secret1234"},
    ).status_code == 201

    for _ in range(2):
        bad = client.post(f"{prefix}/auth/login", data={"username": "lockuser", "password": "wrong"})
        assert bad.status_code == 401

    row = db_session.execute(
        select(UserAuthState).join(User, User.id == UserAuthState.user_id).where(User.username == "lockuser")
    ).scalar_one()
    assert row.failed_login_count == 2
    assert row.locked_until is not None

    locked = client.post(f"{prefix}/auth/login", data={"username": "lockuser", "password": "secret1234"})
    assert locked.status_code == 401
    assert locked.json().get("detail") == "用户名或密码错误"

    row.locked_until = None
    db_session.add(row)
    db_session.commit()
    ok = client.post(f"{prefix}/auth/login", data={"username": "lockuser", "password": "secret1234"})
    assert ok.status_code == 200, ok.text
    db_session.expire_all()
    cleared = db_session.get(UserAuthState, row.user_id)
    assert cleared is not None
    assert cleared.failed_login_count == 0
    assert cleared.locked_until is None
    assert cleared.last_login_at is not None


def test_login_success_writes_structured_security_event(client, db_session):
    prefix = settings.API_V1_PREFIX
    assert client.post(
        f"{prefix}/auth/register",
        json={"email": "audit@example.com", "username": "audituser", "password": "secret1234"},
    ).status_code == 201
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "audituser", "password": "secret1234"},
        headers={"X-Request-ID": "rid-auth-1", "User-Agent": "pytest-agent"},
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    ev = db_session.execute(
        select(SecurityEvent).where(SecurityEvent.event_type == "auth.login.succeeded")
    ).scalars().first()
    assert ev is not None
    assert ev.user_id is not None
    assert ev.request_id == "rid-auth-1"
    assert ev.user_agent == "pytest-agent"


def test_forgot_password_rate_limited_by_ip(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_FORGOT_PER_IP_PER_HOUR", 2)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_FORGOT_PER_EMAIL_PER_HOUR", 100)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    for i in range(2):
        r = client.post(
            f"{prefix}/auth/forgot-password",
            json={"email": f"fp{i}@example.com"},
        )
        assert r.status_code == 200, r.text
    r3 = client.post(f"{prefix}/auth/forgot-password", json={"email": "fp9@example.com"})
    assert r3.status_code == 429
    assert r3.json().get("success") is False


def test_rate_limit_writes_security_event(client, db_session, monkeypatch):
    from sqlalchemy import func, select

    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests
    from app.models.security_event import SecurityEvent

    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_LOGIN_PER_IP_PER_MINUTE", 1)
    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    assert (
        client.post(
            f"{prefix}/auth/login",
            data={"username": "nobody", "password": "wrong"},
        ).status_code
        == 401
    )
    client.post(f"{prefix}/auth/login", data={"username": "nobody", "password": "wrong"})
    db_session.expire_all()
    n = int(db_session.scalar(select(func.count()).select_from(SecurityEvent)) or 0)
    assert n >= 1


def test_login_failure_includes_www_authenticate(client):
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "nobody", "password": "wrongpass12"},
    )
    assert r.status_code == 401
    assert (r.headers.get("www-authenticate") or "").lower().startswith("bearer")


def test_users_me_without_token_includes_www_authenticate(client):
    prefix = settings.API_V1_PREFIX
    r = client.get(f"{prefix}/users/me")
    assert r.status_code == 401
    assert (r.headers.get("www-authenticate") or "").lower().startswith("bearer")


def test_openapi_contains_auth_and_me_paths_when_exposed(client):
    spec = openapi_skip_unless_exposed(client)
    prefix = settings.API_V1_PREFIX
    paths = spec["paths"]
    assert_openapi_paths(
        paths,
        f"{prefix}/auth/register",
        f"{prefix}/auth/login",
        f"{prefix}/auth/forgot-password",
        f"{prefix}/auth/logout",
        f"{prefix}/auth/refresh",
        f"{prefix}/auth/reset-password",
        f"{prefix}/auth/registration-options",
        f"{prefix}/users/me",
    )
    tags = collect_operation_tags(paths)
    assert "auth" in tags
    assert "users" in tags


def test_forgot_password_creates_token_and_reset_password_roundtrip(client, db_session, monkeypatch, caplog):
    import logging
    from urllib.parse import parse_qs, urlparse

    monkeypatch.setattr(config_module.settings, "AUTH_PASSWORD_RESET_EMAIL_BACKEND", "log")
    monkeypatch.setattr(
        config_module.settings,
        "AUTH_PASSWORD_RESET_PUBLIC_LINK_TEMPLATE",
        "https://app.test/reset?token={token}",
    )
    prefix = settings.API_V1_PREFIX
    email = "roundtrip_fp@example.com"
    assert (
        client.post(
            f"{prefix}/auth/register",
            json={"email": email, "username": "roundtrip_fp", "password": "oldSecret12"},
        ).status_code
        == 201
    )
    assert client.post(
        f"{prefix}/auth/login",
        data={"username": email, "password": "oldSecret12"},
    ).status_code == 200
    assert int(db_session.scalar(select(func.count()).select_from(RefreshToken)) or 0) == 1
    with caplog.at_level(logging.INFO):
        r = client.post(f"{prefix}/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    raw_token = None
    for rec in caplog.records:
        msg = rec.getMessage()
        if "https://app.test/reset?token=" not in msg:
            continue
        i = msg.index("https://app.test")
        url = msg[i:].split()[0]
        raw_token = parse_qs(urlparse(url).query)["token"][0]
        break
    assert raw_token and len(raw_token) >= 16, caplog.text
    new_pw = "newSecret345"
    rr = client.post(
        f"{prefix}/auth/reset-password",
        json={"token": raw_token, "password": new_pw},
    )
    assert rr.status_code == 200, rr.text
    db_session.expire_all()
    active_refresh_tokens = int(
        db_session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        or 0
    )
    assert active_refresh_tokens == 0
    assert client.post(
        f"{prefix}/auth/login",
        data={"username": email, "password": new_pw},
    ).status_code == 200
    assert client.post(
        f"{prefix}/auth/login",
        data={"username": email, "password": "oldSecret12"},
    ).status_code == 401


def test_reset_password_rejects_invalid_token(client):
    prefix = settings.API_V1_PREFIX
    r = client.post(
        f"{prefix}/auth/reset-password",
        json={"token": "not-a-valid-token-at-all-xx", "password": "newSecret12"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == "PASSWORD_RESET_INVALID"


def test_login_with_email(client):
    prefix = settings.API_V1_PREFIX
    client.post(
        f"{prefix}/auth/register",
        json={
            "email": "bob@example.com",
            "username": "bob",
            "password": "secret1234",
        },
    )
    r = client.post(
        f"{prefix}/auth/login",
        data={"username": "bob@example.com", "password": "secret1234"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
