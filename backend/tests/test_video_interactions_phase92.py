"""阶段 9.2：点赞与收藏最小测试。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_interaction_codes import (
    VIDEO_FAVORITE_ALREADY_EXISTS,
    VIDEO_FAVORITE_NOT_FOUND,
    VIDEO_INTERACTION_REQUIRES_PUBLISHED,
    VIDEO_LIKE_ALREADY_EXISTS,
    VIDEO_LIKE_NOT_FOUND,
)
from app.models.enums import UserRole
from app.models.user import User
from app.models.video import Video
from app.models.video_favorite import VideoFavorite
from app.models.video_like import VideoLike
from app.repositories import user_repository
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


def _admin(db_session, client):
    user_repository.create_user(
        db_session,
        email="v92adm@example.com",
        username="v92adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "v92adm")


def _publish(client, p: str, vid: uuid.UUID, hdr: dict, ahdr: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200


def test_like_unlike_and_counts_on_published_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92a@example.com", "v92a")
    hdr = _login(client, "v92a")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "x", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)

    r0 = client.get(f"{p}/{vid}")
    assert r0.json()["likes_count"] == 0
    assert r0.json()["favorites_count"] == 0

    r_like = client.post(f"{p}/{vid}/like", headers=hdr)
    assert r_like.status_code == 200
    assert r_like.json()["likes_count"] == 1
    assert r_like.json()["favorites_count"] == 0

    r_detail = client.get(f"{p}/{vid}")
    assert r_detail.json()["likes_count"] == 1

    r_dup = client.post(f"{p}/{vid}/like", headers=hdr)
    assert r_dup.status_code == 409
    assert r_dup.json().get("code") == VIDEO_LIKE_ALREADY_EXISTS

    r_un = client.delete(f"{p}/{vid}/like", headers=hdr)
    assert r_un.status_code == 200
    assert r_un.json()["likes_count"] == 0

    r_nf = client.delete(f"{p}/{vid}/like", headers=hdr)
    assert r_nf.status_code == 404
    assert r_nf.json().get("code") == VIDEO_LIKE_NOT_FOUND


def test_favorite_unfavorite(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92b@example.com", "v92b")
    hdr = _login(client, "v92b")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "f", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)

    r1 = client.post(f"{p}/{vid}/favorite", headers=hdr)
    assert r1.status_code == 200
    assert r1.json()["favorites_count"] == 1
    r_dup = client.post(f"{p}/{vid}/favorite", headers=hdr)
    assert r_dup.status_code == 409
    assert r_dup.json().get("code") == VIDEO_FAVORITE_ALREADY_EXISTS

    r2 = client.delete(f"{p}/{vid}/favorite", headers=hdr)
    assert r2.status_code == 200
    assert r2.json()["favorites_count"] == 0
    r_nf = client.delete(f"{p}/{vid}/favorite", headers=hdr)
    assert r_nf.status_code == 404
    assert r_nf.json().get("code") == VIDEO_FAVORITE_NOT_FOUND


def test_like_draft_requires_published(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92c@example.com", "v92c")
    hdr = _login(client, "v92c")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "d", "tag_ids": []}).json()["id"])
    r = client.post(f"{p}/{vid}/like", headers=hdr)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_INTERACTION_REQUIRES_PUBLISHED


def test_like_pending_review_author_still_requires_published(client, db_session):
    """作者可见待审稿，但点赞/收藏仍须已发布。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92prl@example.com", "v92prl")
    hdr = _login(client, "v92prl")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "prl", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    r_like = client.post(f"{p}/{vid}/like", headers=hdr)
    assert r_like.status_code == 400
    assert r_like.json().get("code") == VIDEO_INTERACTION_REQUIRES_PUBLISHED
    r_fav = client.post(f"{p}/{vid}/favorite", headers=hdr)
    assert r_fav.status_code == 400
    assert r_fav.json().get("code") == VIDEO_INTERACTION_REQUIRES_PUBLISHED


def test_like_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92d@example.com", "v92d")
    hdr = _login(client, "v92d")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "a", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/like").status_code == 401
    assert client.delete(f"{p}/{vid}/like").status_code == 401


def test_favorite_draft_requires_published(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92f@example.com", "v92f")
    hdr = _login(client, "v92f")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "draft-fav", "tag_ids": []}).json()["id"])
    r = client.post(f"{p}/{vid}/favorite", headers=hdr)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_INTERACTION_REQUIRES_PUBLISHED


def test_favorite_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92g@example.com", "v92g")
    hdr = _login(client, "v92g")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "pub-fav", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/favorite").status_code == 401
    assert client.delete(f"{p}/{vid}/favorite").status_code == 401


def test_duplicate_like_keeps_single_db_row(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92h@example.com", "v92h")
    hdr = _login(client, "v92h")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "h", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    uid = db_session.scalar(select(User.id).where(User.username == "v92h"))
    assert uid is not None

    assert client.post(f"{p}/{vid}/like", headers=hdr).status_code == 200
    dup = client.post(f"{p}/{vid}/like", headers=hdr)
    assert dup.status_code == 409
    n = db_session.scalar(
        select(func.count()).select_from(VideoLike).where(VideoLike.user_id == uid, VideoLike.video_id == vid)
    )
    assert n == 1
    assert client.delete(f"{p}/{vid}/like", headers=hdr).status_code == 200
    assert (
        db_session.scalar(
            select(func.count()).select_from(VideoLike).where(VideoLike.user_id == uid, VideoLike.video_id == vid)
        )
        == 0
    )


def test_duplicate_favorite_keeps_single_db_row(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92i@example.com", "v92i")
    hdr = _login(client, "v92i")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "i", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    uid = db_session.scalar(select(User.id).where(User.username == "v92i"))
    assert uid is not None

    assert client.post(f"{p}/{vid}/favorite", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/favorite", headers=hdr).status_code == 409
    n = db_session.scalar(
        select(func.count())
        .select_from(VideoFavorite)
        .where(VideoFavorite.user_id == uid, VideoFavorite.video_id == vid)
    )
    assert n == 1


def test_two_users_like_increments_likes_count(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92j1@example.com", "v92j1")
    _register(client, "v92j2@example.com", "v92j2")
    h1 = _login(client, "v92j1")
    h2 = _login(client, "v92j2")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=h1, json={"title": "j", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, h1, ahdr)
    assert client.post(f"{p}/{vid}/like", headers=h1).status_code == 200
    assert client.post(f"{p}/{vid}/like", headers=h2).status_code == 200
    detail = client.get(f"{p}/{vid}")
    assert detail.json()["likes_count"] == 2


def test_two_users_favorite_increments_favorites_count(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92k1@example.com", "v92k1")
    _register(client, "v92k2@example.com", "v92k2")
    h1 = _login(client, "v92k1")
    h2 = _login(client, "v92k2")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=h1, json={"title": "k", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, h1, ahdr)
    assert client.post(f"{p}/{vid}/favorite", headers=h1).status_code == 200
    assert client.post(f"{p}/{vid}/favorite", headers=h2).status_code == 200
    assert client.get(f"{p}/{vid}").json()["favorites_count"] == 2


def test_like_and_favorite_counts_are_independent(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92m@example.com", "v92m")
    hdr = _login(client, "v92m")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "m", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    like_body = client.post(f"{p}/{vid}/like", headers=hdr).json()
    assert uuid.UUID(like_body["video_id"]) == vid
    assert like_body["likes_count"] == 1 and like_body["favorites_count"] == 0
    body = client.post(f"{p}/{vid}/favorite", headers=hdr).json()
    assert body["likes_count"] == 1 and body["favorites_count"] == 1
    body2 = client.delete(f"{p}/{vid}/like", headers=hdr).json()
    assert body2["likes_count"] == 0 and body2["favorites_count"] == 1
    j = client.get(f"{p}/{vid}").json()
    assert j["likes_count"] == 0 and j["favorites_count"] == 1


def test_get_video_likes_favorites_match_database_row(client, db_session):
    """HTTP 详情中的计数与 ``videos`` 表列一致（经 10.1 统计更新路径）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "v92db@example.com", "v92db")
    hdr = _login(client, "v92db")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "dbcnt", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/like", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/favorite", headers=hdr).status_code == 200
    j = client.get(f"{p}/{vid}", headers=hdr).json()
    row = db_session.execute(select(Video.likes_count, Video.favorites_count).where(Video.id == vid)).one()
    assert j["likes_count"] == int(row[0]) == 1
    assert j["favorites_count"] == int(row[1]) == 1


def test_openapi_contains_video_interaction_routes_when_exposed(client):
    spec = openapi_skip_unless_exposed(client)
    paths = spec.get("paths") or {}
    prefix = settings.API_V1_PREFIX
    assert_openapi_paths(
        paths,
        f"{prefix}/videos/{{video_id}}/like",
        f"{prefix}/videos/{{video_id}}/favorite",
    )
    assert "video-interactions" in collect_operation_tags(paths)
