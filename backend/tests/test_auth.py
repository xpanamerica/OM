from sqlalchemy import select

from app.core import config as config_module
from app.core.config import settings
from app.models.user import User
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
    """限流开启时，同一客户端 IP 超限 POST /auth/login 须 429。"""
    monkeypatch.setattr(config_module.settings, "AUTH_LOGIN_MAX_ATTEMPTS_PER_MINUTE", 2)
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
    assert (r.headers.get("retry-after") or "") == "60"


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
    assert_openapi_paths(paths, f"{prefix}/auth/register", f"{prefix}/auth/login", f"{prefix}/users/me")
    tags = collect_operation_tags(paths)
    assert "auth" in tags
    assert "users" in tags


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
