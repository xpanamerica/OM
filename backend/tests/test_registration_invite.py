"""内测邀请码注册与审计。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core import config as config_module
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.invite_code import InviteCode
from app.models.registration_attempt import RegistrationAttempt
from app.repositories import app_setting_repository, invite_code_repository, user_repository
from app.services import app_settings_service


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, db_session):
    s = uuid.uuid4().hex[:10]
    uname = f"adm{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, uname)


def test_registration_options_default_invite_not_required(client, db_session):
    r = client.get(f"{settings.API_V1_PREFIX}/auth/registration-options")
    assert r.status_code == 200
    assert r.json()["invite_code_required"] is False


def test_register_without_invite_when_not_required(client, db_session):
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": "open@example.com", "username": "openuser", "password": "secret1234"},
    )
    assert r.status_code == 201, r.text
    db_session.expire_all()
    n = int(db_session.scalar(select(func.count()).select_from(RegistrationAttempt)) or 0)
    assert n >= 1


def test_register_missing_invite_when_required(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    assert app_settings_service.is_registration_invite_code_required(db_session) is True

    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": "miss@example.com", "username": "missuser", "password": "secret1234"},
        headers={"User-Agent": "pytest-ua"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "当前为内测阶段，请输入邀请码。"

    db_session.expire_all()
    row = db_session.scalars(select(RegistrationAttempt).order_by(RegistrationAttempt.created_at.desc())).first()
    assert row is not None
    assert row.success is False
    assert row.user_agent == "pytest-ua"


def test_register_with_valid_invite(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    hdr = _admin(client, db_session)
    gen = client.post(
        f"{settings.API_V1_PREFIX}/admin/invite-codes",
        headers=hdr,
        json={"max_uses": 1},
    )
    assert gen.status_code == 200, gen.text
    code = gen.json()["invite"]["code"]

    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "inv@example.com",
            "username": "invuser",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r.status_code == 201, r.text

    db_session.expire_all()
    inv = db_session.scalars(select(InviteCode).where(InviteCode.code == code)).one()
    assert inv.used_count == 1
    assert inv.status == "used"
    assert inv.used_by is not None


def test_register_rejects_used_invite(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    hdr = _admin(client, db_session)
    gen = client.post(
        f"{settings.API_V1_PREFIX}/admin/invite-codes",
        headers=hdr,
        json={"max_uses": 1},
    )
    code = gen.json()["invite"]["code"]
    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={
                "email": "a1@example.com",
                "username": "a1user",
                "password": "secret1234",
                "invite_code": code,
            },
        ).status_code
        == 201
    )
    r2 = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "a2@example.com",
            "username": "a2user",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r2.status_code == 400
    assert "邀请码" in r2.json()["detail"]


def test_register_rejects_expired_invite(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    past = datetime.now(UTC) - timedelta(days=1)
    row = invite_code_repository.create_invite(
        db_session,
        code="DEADBEEF12345678",
        created_by=None,
        expires_at=past,
        max_uses=1,
    )
    db_session.commit()
    code = row.code

    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "exp@example.com",
            "username": "expuser",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "邀请码已过期"


def test_register_respects_auth_register_max_attempts_per_minute(monkeypatch, client, db_session):
    """生产向：AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE>0 时覆盖「每分钟」注册上限（默认 0 不改变既有单测口径）。"""
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 2)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 100)
    monkeypatch.setattr(config_module.settings, "AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE", 3)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()
    prefix = settings.API_V1_PREFIX
    for i in range(3):
        r = client.post(
            f"{prefix}/auth/register",
            json={
                "email": f"cap{i}@example.com",
                "username": f"capuser{i}",
                "password": "secret1234",
            },
        )
        assert r.status_code == 201, r.text
    r4 = client.post(
        f"{prefix}/auth/register",
        json={"email": "cap4@example.com", "username": "capuser4", "password": "secret1234"},
    )
    assert r4.status_code == 429


def test_register_rate_limited_after_max_attempts(monkeypatch, client, db_session):
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_USE_REDIS", False)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_MINUTE", 2)
    monkeypatch.setattr(config_module.settings, "AUTH_RATE_LIMIT_REGISTER_PER_IP_PER_HOUR", 100)
    from app.core.auth_rate_limit import reset_auth_rate_limit_memory_for_tests

    reset_auth_rate_limit_memory_for_tests()

    for i in range(2):
        r = client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={
                "email": f"rl{i}@example.com",
                "username": f"rluser{i}",
                "password": "secret1234",
            },
        )
        assert r.status_code == 201, r.text

    r3 = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": "rl3@example.com", "username": "rluser3", "password": "secret1234"},
    )
    assert r3.status_code == 429
    assert r3.json().get("success") is False
    assert r3.json().get("message")


def test_admin_list_registration_attempts_after_failed_register(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    assert app_settings_service.is_registration_invite_code_required(db_session) is True
    ro = client.get(f"{settings.API_V1_PREFIX}/auth/registration-options")
    assert ro.status_code == 200 and ro.json()["invite_code_required"] is True
    hdr = _admin(client, db_session)

    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={"email": "aud@example.com", "username": "auduser", "password": "secret1234"},
        ).status_code
        == 400
    )

    r = client.get(f"{settings.API_V1_PREFIX}/admin/registration-attempts", headers=hdr, params={"limit": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert any(row.get("email") == "aud@example.com" and row.get("success") is False for row in body["items"])


def test_admin_generated_invite_code_has_sufficient_length(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    hdr = _admin(client, db_session)
    gen = client.post(
        f"{settings.API_V1_PREFIX}/admin/invite-codes",
        headers=hdr,
        json={"max_uses": 1},
    )
    assert gen.status_code == 200, gen.text
    code = gen.json()["invite"]["code"]
    assert len(code) >= 20
    assert code.isalnum()
