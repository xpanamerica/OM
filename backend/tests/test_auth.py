from sqlalchemy import select
from pydantic import SecretStr

from app.core import config as config_module
from app.core.config import settings
from app.models.user import User
from app.services import turnstile_service
from tests.support.openapi_contracts import assert_openapi_paths, collect_operation_tags, openapi_skip_unless_exposed


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
    assert r.status_code == 429
    assert r.json().get("success") is False


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
    assert r.status_code == 429
    assert r.json().get("success") is False


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
