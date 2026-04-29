"""邀请码 max_uses > 1 时可多次注册。"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.invite_code import InviteCode
from app.repositories import app_setting_repository, user_repository


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, db_session):
    s = uuid.uuid4().hex[:8]
    uname = f"madm{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, uname)


def test_invite_max_uses_two_allows_two_registrations(client, db_session):
    app_setting_repository.set_value(db_session, key="registration_invite_code_required", value="true")
    db_session.commit()
    hdr = _admin(client, db_session)
    gen = client.post(
        f"{settings.API_V1_PREFIX}/admin/invite-codes",
        headers=hdr,
        json={"max_uses": 2},
    )
    assert gen.status_code == 200, gen.text
    code = gen.json()["invite"]["code"]

    r1 = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "m1@example.com",
            "username": "m1user",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "m2@example.com",
            "username": "m2user",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r2.status_code == 201, r2.text

    db_session.expire_all()
    row = db_session.scalars(select(InviteCode).where(InviteCode.code == code)).one()
    assert row.used_count == 2
    assert row.status == "used"

    r3 = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "m3@example.com",
            "username": "m3user",
            "password": "secret1234",
            "invite_code": code,
        },
    )
    assert r3.status_code == 400
