"""阶段 10.3：全链路最小可回归测试（pytest）。

前提：核心业务已完成；本文件只补测试，不修改业务逻辑。
依赖 ``tests/conftest.py``（SQLite 共享内存库 + ``get_db`` 覆盖），不访问真实外网服务。
"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.repositories import user_repository


def _prefix() -> str:
    return settings.API_V1_PREFIX


def _register(client, *, email: str, username: str, password: str = "secret1234") -> None:
    r = client.post(
        f"{_prefix()}/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert r.status_code == 201, r.text


def _login(client, *, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{_prefix()}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin_headers(db_session, client) -> dict[str, str]:
    s = uuid.uuid4().hex[:8]
    uname = f"p103adm{s}"
    user_repository.create_user(
        db_session,
        email=f"{uname}@example.com",
        username=uname,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, username=uname)


def _publish(client, p: str, vid: uuid.UUID, author_hdr: dict[str, str], admin_hdr: dict[str, str]) -> None:
    assert client.post(f"{p}/{vid}/submit-review", headers=author_hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=admin_hdr).status_code == 200


# ---------------------------------------------------------------------------
# 1. Auth
# ---------------------------------------------------------------------------


def test_phase103_auth_register_success(client):
    _register(client, email="p103reg1@example.com", username="p103reg1")


def test_phase103_auth_register_duplicate_fails(client):
    _register(client, email="p103dup@example.com", username="p103dup")
    r2 = client.post(
        f"{_prefix()}/auth/register",
        json={"email": "p103dup@example.com", "username": "p103dup_other", "password": "secret1234"},
    )
    assert r2.status_code == 409


def test_phase103_auth_login_success(client):
    _register(client, email="p103log@example.com", username="p103log")
    r = client.post(
        f"{_prefix()}/auth/login",
        data={"username": "p103log", "password": "secret1234"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_phase103_auth_login_wrong_password_fails(client):
    _register(client, email="p103bad@example.com", username="p103bad")
    r = client.post(
        f"{_prefix()}/auth/login",
        data={"username": "p103bad", "password": "wrong-password-xyz"},
    )
    assert r.status_code == 401


def test_phase103_auth_me_success(client):
    _register(client, email="p103me@example.com", username="p103me")
    hdr = _login(client, username="p103me")
    r = client.get(f"{_prefix()}/users/me", headers=hdr)
    assert r.status_code == 200
    assert r.json()["username"] == "p103me"


def test_phase103_auth_me_without_token_fails(client):
    r = client.get(f"{_prefix()}/users/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. Category / Tag
# ---------------------------------------------------------------------------


def test_phase103_categories_admin_create_user_forbidden_list_public(client, db_session):
    p = _prefix()
    ahdr = _admin_headers(db_session, client)
    _register(client, email="p103catu@example.com", username="p103catu")
    uhdr = _login(client, username="p103catu")

    r_ok = client.post(
        f"{p}/categories",
        headers=ahdr,
        json={"name": f"p103-cat-{uuid.uuid4().hex[:6]}", "description": "d"},
    )
    assert r_ok.status_code == 201, r_ok.text

    r_forbidden = client.post(
        f"{p}/categories",
        headers=uhdr,
        json={"name": "p103-cat-user", "description": "x"},
    )
    assert r_forbidden.status_code == 403

    r_list = client.get(f"{p}/categories")
    assert r_list.status_code == 200
    assert isinstance(r_list.json(), list)


def test_phase103_tags_admin_create_user_forbidden_list_public(client, db_session):
    p = _prefix()
    ahdr = _admin_headers(db_session, client)
    _register(client, email="p103tagu@example.com", username="p103tagu")
    uhdr = _login(client, username="p103tagu")

    r_ok = client.post(f"{p}/tags", headers=ahdr, json={"name": f"p103-tag-{uuid.uuid4().hex[:6]}"})
    assert r_ok.status_code == 201, r_ok.text

    r_forbidden = client.post(f"{p}/tags", headers=uhdr, json={"name": "p103-tag-user"})
    assert r_forbidden.status_code == 403

    r_list = client.get(f"{p}/tags")
    assert r_list.status_code == 200
    assert isinstance(r_list.json(), list)


# ---------------------------------------------------------------------------
# 3. Video
# ---------------------------------------------------------------------------


def test_phase103_video_user_creates_draft_author_sees_stranger_not(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103v1a@example.com", username="p103v1a")
    _register(client, email="p103v1b@example.com", username="p103v1b")
    ha = _login(client, username="p103v1a")
    hb = _login(client, username="p103v1b")
    r = client.post(pv, headers=ha, json={"title": "draft p103", "tag_ids": []})
    assert r.status_code == 201
    vid = uuid.UUID(r.json()["id"])
    assert r.json()["status"] == "draft"

    r_author = client.get(f"{pv}/{vid}", headers=ha)
    assert r_author.status_code == 200
    assert r_author.json()["status"] == "draft"

    r_stranger = client.get(f"{pv}/{vid}", headers=hb)
    assert r_stranger.status_code == 404


def test_phase103_video_published_anonymous_visible(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103vpub@example.com", username="p103vpub")
    hdr = _login(client, username="p103vpub")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "pub p103", "tag_ids": []}).json()["id"])
    _publish(client, pv, vid, hdr, adm)
    r = client.get(f"{pv}/{vid}")
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_phase103_video_submit_and_admin_approve(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103vap@example.com", username="p103vap")
    hdr = _login(client, username="p103vap")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "approve flow", "tag_ids": []}).json()["id"])
    r1 = client.post(f"{pv}/{vid}/submit-review", headers=hdr)
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending_review"
    r2 = client.post(f"{pv}/{vid}/approve", headers=adm)
    assert r2.status_code == 200
    assert r2.json()["status"] == "published"


def test_phase103_video_submit_and_admin_reject(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103vrj@example.com", username="p103vrj")
    hdr = _login(client, username="p103vrj")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "reject flow", "tag_ids": []}).json()["id"])
    assert client.post(f"{pv}/{vid}/submit-review", headers=hdr).status_code == 200
    rr = client.post(
        f"{pv}/{vid}/reject",
        headers=adm,
        json={"rejection_reason": "p103 测试驳回"},
    )
    assert rr.status_code == 200
    assert rr.json()["status"] == "rejected"


def test_phase103_video_admin_offline_after_publish(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103vof@example.com", username="p103vof")
    hdr = _login(client, username="p103vof")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "offline flow", "tag_ids": []}).json()["id"])
    _publish(client, pv, vid, hdr, adm)
    ro = client.post(f"{pv}/{vid}/offline", headers=adm)
    assert ro.status_code == 200
    assert ro.json()["status"] == "offline"


# ---------------------------------------------------------------------------
# 4. Comment
# ---------------------------------------------------------------------------


def test_phase103_comment_on_published_requires_auth_author_and_admin_soft_delete(client, db_session):
    pv = f"{_prefix()}/videos"
    pc = f"{_prefix()}/comments"
    _register(client, email="p103cm@example.com", username="p103cm")
    _register(client, email="p103cm2@example.com", username="p103cm2")
    author = _login(client, username="p103cm")
    other = _login(client, username="p103cm2")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=author, json={"title": "cmt video", "tag_ids": []}).json()["id"])
    _publish(client, pv, vid, author, adm)

    r_noauth = client.post(f"{pv}/{vid}/comments", json={"content": "nope"})
    assert r_noauth.status_code == 401

    r_post = client.post(f"{pv}/{vid}/comments", headers=author, json={"content": "  hello p103  "})
    assert r_post.status_code == 200
    cid = uuid.UUID(r_post.json()["id"])
    assert r_post.json()["content"] == "hello p103"

    assert client.delete(f"{pc}/{cid}", headers=author).status_code == 204

    cid2 = uuid.UUID(
        client.post(f"{pv}/{vid}/comments", headers=other, json={"content": "for admin"}).json()["id"]
    )
    assert client.delete(f"{pc}/{cid2}", headers=adm).status_code == 204


# ---------------------------------------------------------------------------
# 5. Like / Favorite
# ---------------------------------------------------------------------------


def test_phase103_like_favorite_success_duplicate_no_extra_count_cancel_ok(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103lk@example.com", username="p103lk")
    hdr = _login(client, username="p103lk")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "like fav", "tag_ids": []}).json()["id"])
    _publish(client, pv, vid, hdr, adm)

    r_like = client.post(f"{pv}/{vid}/like", headers=hdr)
    assert r_like.status_code == 200
    assert r_like.json()["likes_count"] == 1

    r_dup = client.post(f"{pv}/{vid}/like", headers=hdr)
    assert r_dup.status_code == 409
    assert client.get(f"{pv}/{vid}").json()["likes_count"] == 1

    r_un = client.delete(f"{pv}/{vid}/like", headers=hdr)
    assert r_un.status_code == 200
    assert r_un.json()["likes_count"] == 0

    r_fav = client.post(f"{pv}/{vid}/favorite", headers=hdr)
    assert r_fav.status_code == 200
    assert r_fav.json()["favorites_count"] == 1

    r_fdup = client.post(f"{pv}/{vid}/favorite", headers=hdr)
    assert r_fdup.status_code == 409
    assert client.get(f"{pv}/{vid}").json()["favorites_count"] == 1

    r_unf = client.delete(f"{pv}/{vid}/favorite", headers=hdr)
    assert r_unf.status_code == 200
    assert r_unf.json()["favorites_count"] == 0


# ---------------------------------------------------------------------------
# 6. ViewRecord
# ---------------------------------------------------------------------------


def test_phase103_view_record_first_then_update_views_count_increments_once(client, db_session):
    pv = f"{_prefix()}/videos"
    _register(client, email="p103vr@example.com", username="p103vr")
    hdr = _login(client, username="p103vr")
    adm = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(pv, headers=hdr, json={"title": "view rec", "tag_ids": []}).json()["id"])
    _publish(client, pv, vid, hdr, adm)

    assert client.get(f"{pv}/{vid}").json()["views_count"] == 0

    r1 = client.post(f"{pv}/{vid}/view-record", headers=hdr, json={"progress_seconds": 3})
    assert r1.status_code == 200
    assert r1.json()["progress_seconds"] == 3
    assert client.get(f"{pv}/{vid}").json()["views_count"] == 1

    r2 = client.post(f"{pv}/{vid}/view-record", headers=hdr, json={"progress_seconds": 99})
    assert r2.status_code == 200
    assert r2.json()["progress_seconds"] == 99
    assert client.get(f"{pv}/{vid}").json()["views_count"] == 1
