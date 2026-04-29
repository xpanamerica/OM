"""阶段 10.2：管理员内容管理增强最小测试。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole, VideoStatus
from app.models.user import User
from app.models.video import Video
from app.repositories import user_repository
from app.services import admin_management_service
from tests.support.openapi_contracts import assert_openapi_paths, collect_operation_tags, openapi_skip_unless_exposed


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _register(client, email: str, username: str):
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": email, "username": username, "password": "secret1234"},
    )
    assert r.status_code == 201, r.text


def _admin_hdr(db_session, client) -> dict[str, str]:
    s = uuid.uuid4().hex[:10]
    uname = f"a{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, uname)


def test_non_admin_all_admin_endpoints_return_403(client, db_session):
    _register(client, "u102@example.com", "u102")
    hdr = _login(client, "u102")
    base = f"{settings.API_V1_PREFIX}/admin"
    assert client.get(f"{base}/videos", headers=hdr).status_code == 403
    assert client.get(f"{base}/users", headers=hdr).status_code == 403
    assert client.get(f"{base}/invite-codes", headers=hdr).status_code == 403
    assert client.post(f"{base}/invite-codes", headers=hdr, json={"max_uses": 1}).status_code == 403
    assert (
        client.post(f"{base}/invite-codes/{uuid.uuid4()}/revoke", headers=hdr).status_code == 403
    )
    assert client.get(f"{base}/registration-attempts", headers=hdr).status_code == 403
    assert client.get(f"{base}/statistics/platform", headers=hdr).status_code == 403
    uid = str(uuid.uuid4())
    assert client.patch(f"{base}/users/{uid}/active", headers=hdr, json={"is_active": False}).status_code == 403
    assert client.delete(f"{base}/users/{uid}", headers=hdr).status_code == 403
    assert client.delete(f"{base}/users/inactive", headers=hdr).status_code == 403


def test_admin_list_videos_filter_status(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    adm = _admin_hdr(db_session, client)
    _register(client, "au102@example.com", "au102")
    uh = _login(client, "au102")
    vid = uuid.UUID(client.post(p, headers=uh, json={"title": "draftonly", "tag_ids": []}).json()["id"])
    r = client.get(f"{settings.API_V1_PREFIX}/admin/videos", headers=adm, params={"status": "draft"})
    assert r.status_code == 200
    assert r.headers.get("X-Total-Count") == "1"
    ids = {row["id"] for row in r.json()}
    assert str(vid) in ids


def test_admin_list_videos_filter_pending_review(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    adm = _admin_hdr(db_session, client)
    _register(client, "pr102@example.com", "pr102")
    uh = _login(client, "pr102")
    vid = uuid.UUID(client.post(p, headers=uh, json={"title": "pendchk", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=uh).status_code == 200
    r = client.get(
        f"{settings.API_V1_PREFIX}/admin/videos",
        headers=adm,
        params={"status": "pending_review"},
    )
    assert r.status_code == 200
    body = r.json()
    assert str(vid) in {row["id"] for row in body}
    assert all(row["status"] == "pending_review" for row in body)


def test_admin_list_users_keyword(client, db_session):
    adm = _admin_hdr(db_session, client)
    _register(client, "kw102@example.com", "kwuser102")
    r = client.get(
        f"{settings.API_V1_PREFIX}/admin/users",
        headers=adm,
        params={"keyword": "kw102"},
    )
    assert r.status_code == 200
    assert int(r.headers.get("X-Total-Count", "0")) >= 1
    assert any("kw102" in row["email"] for row in r.json())


def test_admin_platform_statistics_matches_db_and_http(client, db_session):
    """HTTP 响应与 ``get_platform_statistics`` 及 ORM 独立计数三者一致。"""
    adm = _admin_hdr(db_session, client)
    svc = admin_management_service.get_platform_statistics(db_session)
    u_alive = int(db_session.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0)
    v_total = int(db_session.scalar(select(func.count(Video.id))) or 0)
    v_pub = int(
        db_session.scalar(select(func.count(Video.id)).where(Video.status == VideoStatus.PUBLISHED)) or 0
    )
    v_pend = int(
        db_session.scalar(select(func.count(Video.id)).where(Video.status == VideoStatus.PENDING_REVIEW)) or 0
    )
    row = db_session.execute(
        select(
            func.coalesce(func.sum(Video.views_count), 0),
            func.coalesce(func.sum(Video.likes_count), 0),
            func.coalesce(func.sum(Video.favorites_count), 0),
        ).select_from(Video)
    ).one()
    assert svc.users_total == u_alive
    assert svc.videos_total == v_total
    assert svc.videos_published == v_pub
    assert svc.videos_pending_review == v_pend
    assert svc.total_views_count == int(row[0])
    assert svc.total_likes_count == int(row[1])
    assert svc.total_favorites_count == int(row[2])

    r = client.get(f"{settings.API_V1_PREFIX}/admin/statistics/platform", headers=adm)
    assert r.status_code == 200
    j = r.json()
    assert j["users_total"] == svc.users_total
    assert j["videos_total"] == svc.videos_total
    assert j["videos_published"] == svc.videos_published
    assert j["videos_pending_review"] == svc.videos_pending_review
    assert j["total_views_count"] == svc.total_views_count
    assert j["total_likes_count"] == svc.total_likes_count
    assert j["total_favorites_count"] == svc.total_favorites_count


def test_openapi_contains_admin_routes_when_exposed(client):
    spec = openapi_skip_unless_exposed(client)
    paths = spec.get("paths") or {}
    prefix = settings.API_V1_PREFIX
    assert_openapi_paths(
        paths,
        f"{prefix}/admin/videos",
        f"{prefix}/admin/users",
        f"{prefix}/admin/invite-codes",
        f"{prefix}/admin/invite-codes/{{invite_id}}/revoke",
        f"{prefix}/admin/registration-attempts",
        f"{prefix}/admin/statistics/platform",
        f"{prefix}/admin/users/{{user_id}}/active",
        f"{prefix}/admin/users/{{user_id}}",
        f"{prefix}/admin/users/inactive",
    )
    assert "admin" in collect_operation_tags(paths)


def test_admin_disable_user_blocks_login(client, db_session):
    adm = _admin_hdr(db_session, client)
    _register(client, "dis102@example.com", "dis102")
    uh = _login(client, "dis102")
    uid = None
    r_users = client.get(f"{settings.API_V1_PREFIX}/admin/users", headers=adm, params={"keyword": "dis102"})
    for row in r_users.json():
        if row["username"] == "dis102":
            uid = row["id"]
            break
    assert uid is not None
    r_patch = client.patch(
        f"{settings.API_V1_PREFIX}/admin/users/{uid}/active",
        headers=adm,
        json={"is_active": False},
    )
    assert r_patch.status_code == 200, r_patch.text
    r_login = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "dis102", "password": "secret1234"},
    )
    assert r_login.status_code == 401


def test_admin_cannot_disable_self(client, db_session):
    s = uuid.uuid4().hex[:10]
    uname = f"s{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    adm = _login(client, uname)
    r_users = client.get(f"{settings.API_V1_PREFIX}/admin/users", headers=adm, params={"keyword": uname})
    uid = next(row["id"] for row in r_users.json() if row["username"] == uname)
    r = client.patch(
        f"{settings.API_V1_PREFIX}/admin/users/{uid}/active",
        headers=adm,
        json={"is_active": False},
    )
    assert r.status_code == 403


def test_admin_delete_user_soft_deletes_and_blocks_login(client, db_session):
    adm = _admin_hdr(db_session, client)
    _register(client, "deluser102@example.com", "deluser102")
    assert _login(client, "deluser102")
    r_users = client.get(
        f"{settings.API_V1_PREFIX}/admin/users",
        headers=adm,
        params={"keyword": "deluser102"},
    )
    uid = next(row["id"] for row in r_users.json() if row["username"] == "deluser102")

    r = client.delete(f"{settings.API_V1_PREFIX}/admin/users/{uid}", headers=adm)
    assert r.status_code == 204, r.text

    row = db_session.execute(select(User).where(User.id == uuid.UUID(uid))).scalar_one()
    assert row.deleted_at is not None
    assert row.is_active is False

    r_login = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "deluser102", "password": "secret1234"},
    )
    assert r_login.status_code == 401
    r_after = client.get(
        f"{settings.API_V1_PREFIX}/admin/users",
        headers=adm,
        params={"keyword": "deluser102"},
    )
    assert all(row["id"] != uid for row in r_after.json())


def test_admin_cannot_delete_self(client, db_session):
    s = uuid.uuid4().hex[:10]
    uname = f"ds{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    adm = _login(client, uname)
    r_users = client.get(f"{settings.API_V1_PREFIX}/admin/users", headers=adm, params={"keyword": uname})
    uid = next(row["id"] for row in r_users.json() if row["username"] == uname)
    r = client.delete(f"{settings.API_V1_PREFIX}/admin/users/{uid}", headers=adm)
    assert r.status_code == 403


def test_admin_delete_inactive_users_soft_deletes_only_disabled_accounts(client, db_session):
    adm = _admin_hdr(db_session, client)
    for idx in range(2):
        user_repository.create_user(
            db_session,
            email=f"inactive-bulk-{idx}@example.com",
            username=f"inactivebulk{idx}",
            hashed_password=get_password_hash("secret1234"),
            is_active=False,
        )
    active = user_repository.create_user(
        db_session,
        email="active-bulk@example.com",
        username="activebulk",
        hashed_password=get_password_hash("secret1234"),
        is_active=True,
    )
    db_session.commit()

    r = client.delete(f"{settings.API_V1_PREFIX}/admin/users/inactive", headers=adm)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 2

    inactive_rows = db_session.execute(
        select(User).where(User.username.in_(["inactivebulk0", "inactivebulk1"]))
    ).scalars().all()
    assert len(inactive_rows) == 2
    assert all(row.deleted_at is not None for row in inactive_rows)
    db_session.refresh(active)
    assert active.deleted_at is None
    assert active.is_active is True

    r_again = client.delete(f"{settings.API_V1_PREFIX}/admin/users/inactive", headers=adm)
    assert r_again.status_code == 200
    assert r_again.json()["deleted"] == 0


def test_admin_delete_video_returns_204_and_removes_row(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    adm = _admin_hdr(db_session, client)
    _register(client, "del102@example.com", "del102")
    uh = _login(client, "del102")
    vid = str(uuid.UUID(client.post(p, headers=uh, json={"title": "todelete", "tag_ids": []}).json()["id"]))
    r = client.delete(f"{p}/{vid}", headers=adm)
    assert r.status_code == 204, r.text
    assert client.get(f"{p}/{vid}", headers=uh).status_code == 404


def test_non_admin_cannot_delete_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    adm = _admin_hdr(db_session, client)
    _register(client, "nd102@example.com", "nd102")
    uh = _login(client, "nd102")
    vid = str(uuid.UUID(client.post(p, headers=uh, json={"title": "keepme", "tag_ids": []}).json()["id"]))
    assert client.delete(f"{p}/{vid}", headers=uh).status_code == 403
    r = client.delete(f"{p}/{vid}", headers=adm)
    assert r.status_code == 204
