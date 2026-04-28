"""个人中心聚合与关注。"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole, VideoStatus
from app.models.video import Video
from app.repositories import user_repository


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


def test_profile_hub_empty_and_follow_counts(client, db_session):
    p = f"{settings.API_V1_PREFIX}/users"
    _register(client, "hub1@example.com", "hub1user")
    _register(client, "hub2@example.com", "hub2user")
    h1 = _login(client, "hub1user")
    h2 = _login(client, "hub2user")

    r_hub = client.get(f"{p}/me/profile-hub", headers=h1)
    assert r_hub.status_code == 200, r_hub.text
    j = r_hub.json()
    assert j["following_count"] == 0
    assert j["followers_count"] == 0
    assert j["likes_and_favorites_received"] == 0
    assert j["recent_videos"] == []

    me2 = client.get(f"{p}/me", headers=h2).json()
    fid = uuid.UUID(me2["id"])

    assert client.post(f"{p}/{fid}/follow", headers=h1).status_code == 204
    j1 = client.get(f"{p}/me/profile-hub", headers=h1).json()
    assert j1["following_count"] == 1
    j2 = client.get(f"{p}/me/profile-hub", headers=h2).json()
    assert j2["followers_count"] == 1

    assert client.delete(f"{p}/{fid}/follow", headers=h1).status_code == 204


def test_profile_hub_likes_received_on_published(client, db_session):
    _register(client, "hub3@example.com", "hub3author")
    hdr = _login(client, "hub3author")
    uid = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=hdr).json()["id"])
    v = Video(
        title="t",
        description=None,
        cover_url=None,
        video_url=None,
        author_id=uid,
        category_id=None,
        status=VideoStatus.PUBLISHED,
        likes_count=3,
        favorites_count=7,
    )
    db_session.add(v)
    db_session.commit()

    r = client.get(f"{settings.API_V1_PREFIX}/users/me/profile-hub", headers=hdr)
    assert r.status_code == 200
    assert r.json()["likes_and_favorites_received"] == 10


def test_follow_self_400(client, db_session):
    _register(client, "hub4@example.com", "hub4user")
    hdr = _login(client, "hub4user")
    uid = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=hdr).json()["id"])
    assert client.post(f"{settings.API_V1_PREFIX}/users/{uid}/follow", headers=hdr).status_code == 400


def test_videos_followed_only_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    r = client.get(p, params={"followed_only": "true", "limit": 5})
    assert r.status_code == 401, r.text


def test_videos_followed_only_empty_when_no_follows(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "ff1@example.com", "ffollow1")
    hdr = _login(client, "ffollow1")
    r = client.get(p, params={"followed_only": "true", "limit": 20}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json() == []
    assert r.headers.get("X-Total-Count") == "0"


def test_videos_followed_only_returns_followee_video(client, db_session):
    vp = f"{settings.API_V1_PREFIX}/videos"
    user_repository.create_user(
        db_session,
        email="ffadm@example.com",
        username="ffadm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    adm = _login(client, "ffadm", "secret1234")

    _register(client, "ffa@example.com", "ffauthor")
    _register(client, "ffb@example.com", "ffreader")
    ha = _login(client, "ffauthor")
    hr = _login(client, "ffreader")
    author_me = client.get(f"{settings.API_V1_PREFIX}/users/me", headers=ha).json()
    author_id = uuid.UUID(author_me["id"])
    vid = client.post(vp, headers=ha, json={"title": "from followee", "tag_ids": []}).json()["id"]
    assert client.post(f"{vp}/{vid}/submit-review", headers=ha).status_code == 200
    assert client.post(f"{vp}/{vid}/approve", headers=adm).status_code == 200

    assert client.post(f"{settings.API_V1_PREFIX}/users/{author_id}/follow", headers=hr).status_code == 204
    r = client.get(vp, params={"followed_only": "true", "limit": 20}, headers=hr)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 1
    assert any(x["id"] == vid for x in rows)
