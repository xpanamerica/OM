"""阶段 10.1：videos 统计字段与真实写路径一致性。"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_interaction_codes import VIDEO_FAVORITE_NOT_FOUND, VIDEO_LIKE_NOT_FOUND
from app.models.enums import UserRole, VideoStatus
from app.models.video import Video
from app.repositories import user_repository
from app.services import video_statistics_service


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


def _admin(db_session, client):
    user_repository.create_user(
        db_session,
        email="p101adm@example.com",
        username="p101adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "p101adm")


def _publish(client, p: str, vid: uuid.UUID, hdr: dict, ahdr: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200


def test_unlike_without_like_returns_404_and_likes_unchanged(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101a@example.com", "p101a")
    hdr = _login(client, "p101a")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "x", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.get(f"{p}/{vid}").json()["likes_count"] == 0
    r = client.delete(f"{p}/{vid}/like", headers=hdr)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_LIKE_NOT_FOUND
    assert client.get(f"{p}/{vid}").json()["likes_count"] == 0


def test_double_unlike_second_returns_404_count_stays_zero(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101b@example.com", "p101b")
    hdr = _login(client, "p101b")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "y", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/like", headers=hdr).status_code == 200
    assert client.delete(f"{p}/{vid}/like", headers=hdr).status_code == 200
    r2 = client.delete(f"{p}/{vid}/like", headers=hdr)
    assert r2.status_code == 404
    assert client.get(f"{p}/{vid}").json()["likes_count"] == 0


def test_unfavorite_without_favorite_returns_404_and_favorites_unchanged(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101c@example.com", "p101c")
    hdr = _login(client, "p101c")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "z", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    r = client.delete(f"{p}/{vid}/favorite", headers=hdr)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_FAVORITE_NOT_FOUND
    assert client.get(f"{p}/{vid}").json()["favorites_count"] == 0


def test_video_statistics_service_clamps_likes_at_zero(db_session):
    """直接调用统计 service：在 likes 行缺失时多次 -1 不得把计数打成负数。"""
    user_repository.create_user(
        db_session,
        email="p101d@example.com",
        username="p101d",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    u = user_repository.get_by_email(db_session, "p101d@example.com")
    assert u is not None
    vid = uuid.uuid4()
    db_session.add(
        Video(
            id=vid,
            title="stat",
            author_id=u.id,
            status=VideoStatus.PUBLISHED,
            likes_count=0,
            favorites_count=0,
            views_count=0,
        )
    )
    db_session.commit()
    video_statistics_service.adjust_likes_count(db_session, video_id=vid, delta=-1)
    video_statistics_service.adjust_likes_count(db_session, video_id=vid, delta=-1)
    db_session.commit()
    lc = db_session.scalar(select(Video.likes_count).where(Video.id == vid))
    assert int(lc or 0) == 0


def test_video_statistics_service_rejects_invalid_delta(db_session):
    user_repository.create_user(
        db_session,
        email="p101e@example.com",
        username="p101e",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    u = user_repository.get_by_email(db_session, "p101e@example.com")
    assert u is not None
    vid = uuid.uuid4()

    db_session.add(
        Video(
            id=vid,
            title="e",
            author_id=u.id,
            status=VideoStatus.PUBLISHED,
            likes_count=1,
            favorites_count=0,
            views_count=0,
        )
    )
    db_session.commit()
    with pytest.raises(ValueError, match="likes_count"):
        video_statistics_service.adjust_likes_count(db_session, video_id=vid, delta=2)


def test_video_statistics_service_clamps_favorites_at_zero(db_session):
    """``favorites_count`` 多次 -1 不得打成负数。"""
    user_repository.create_user(
        db_session,
        email="p101f0@example.com",
        username="p101f0",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    u = user_repository.get_by_email(db_session, "p101f0@example.com")
    assert u is not None
    vid = uuid.uuid4()
    db_session.add(
        Video(
            id=vid,
            title="fav0",
            author_id=u.id,
            status=VideoStatus.PUBLISHED,
            likes_count=0,
            favorites_count=0,
            views_count=0,
        )
    )
    db_session.commit()
    video_statistics_service.adjust_favorites_count(db_session, video_id=vid, delta=-1)
    video_statistics_service.adjust_favorites_count(db_session, video_id=vid, delta=-1)
    db_session.commit()
    fc = db_session.scalar(select(Video.favorites_count).where(Video.id == vid))
    assert int(fc or 0) == 0


def test_video_statistics_service_rejects_invalid_delta_favorites(db_session):
    user_repository.create_user(
        db_session,
        email="p101f1@example.com",
        username="p101f1",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    u = user_repository.get_by_email(db_session, "p101f1@example.com")
    assert u is not None
    vid = uuid.uuid4()
    db_session.add(
        Video(
            id=vid,
            title="f1",
            author_id=u.id,
            status=VideoStatus.PUBLISHED,
            likes_count=0,
            favorites_count=1,
            views_count=0,
        )
    )
    db_session.commit()
    with pytest.raises(ValueError, match="favorites_count"):
        video_statistics_service.adjust_favorites_count(db_session, video_id=vid, delta=2)


def test_increment_views_count_accumulates(db_session):
    user_repository.create_user(
        db_session,
        email="p101v@example.com",
        username="p101v",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    u = user_repository.get_by_email(db_session, "p101v@example.com")
    assert u is not None
    vid = uuid.uuid4()
    db_session.add(
        Video(
            id=vid,
            title="vc",
            author_id=u.id,
            status=VideoStatus.PUBLISHED,
            likes_count=0,
            favorites_count=0,
            views_count=0,
        )
    )
    db_session.commit()
    video_statistics_service.increment_views_count(db_session, video_id=vid)
    video_statistics_service.increment_views_count(db_session, video_id=vid)
    db_session.commit()
    vc = db_session.scalar(select(Video.views_count).where(Video.id == vid))
    assert int(vc or 0) == 2


def test_double_unfavorite_second_returns_404_favorites_unchanged(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101f2@example.com", "p101f2")
    hdr = _login(client, "p101f2")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "unf2", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/favorite", headers=hdr).status_code == 200
    assert client.delete(f"{p}/{vid}/favorite", headers=hdr).status_code == 200
    r2 = client.delete(f"{p}/{vid}/favorite", headers=hdr)
    assert r2.status_code == 404
    assert r2.json().get("code") == VIDEO_FAVORITE_NOT_FOUND
    assert client.get(f"{p}/{vid}").json()["favorites_count"] == 0


def test_unfavorite_without_favorite_returns_404_and_favorites_unchanged(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101f3@example.com", "p101f3")
    hdr = _login(client, "p101f3")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "unf3", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.get(f"{p}/{vid}").json()["favorites_count"] == 0
    r = client.delete(f"{p}/{vid}/favorite", headers=hdr)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_FAVORITE_NOT_FOUND
    assert client.get(f"{p}/{vid}").json()["favorites_count"] == 0


def test_http_video_counts_align_with_db_after_like_favorite_cycle(client, db_session):
    """完整 HTTP 写路径后，详情计数与 ``Video`` 行一致。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p101http@example.com", "p101http")
    hdr = _login(client, "p101http")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "http101", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/like", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/favorite", headers=hdr).status_code == 200
    assert client.delete(f"{p}/{vid}/like", headers=hdr).status_code == 200
    j = client.get(f"{p}/{vid}", headers=hdr).json()
    row = db_session.execute(select(Video.likes_count, Video.favorites_count).where(Video.id == vid)).one()
    assert j["likes_count"] == int(row[0]) == 0
    assert j["favorites_count"] == int(row[1]) == 1
