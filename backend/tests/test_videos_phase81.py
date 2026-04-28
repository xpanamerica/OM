"""阶段 8.1：视频基础信息 API 最小测试。"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_codes import (
    VIDEO_IDEMPOTENCY_BACKEND_UNAVAILABLE,
    VIDEO_IDEMPOTENCY_CONFLICT,
    VIDEO_STATUS_QUERY_FORBIDDEN,
)
from app.models.enums import UserRole, VideoStatus
from app.models.video import Video
from app.repositories import user_repository
from tests.support.openapi_contracts import openapi_skip_unless_exposed


def _login(client, username: str, password: str) -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _register(client, email: str, username: str, password: str = "secret1234"):
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert r.status_code == 201, r.text


def _admin(db_session, client):
    user_repository.create_user(
        db_session,
        email="vadm@example.com",
        username="vadm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "vadm", "secret1234")


def _publish_via_review(client, p: str, vid, author_hdr: dict, admin_hdr: dict):
    """阶段 8.2：draft → submit-review → approve → published。"""
    vid = str(vid)
    r1 = client.post(f"{p}/{vid}/submit-review", headers=author_hdr)
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "pending_review"
    r2 = client.post(f"{p}/{vid}/approve", headers=admin_hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "published"
    return r2


def test_create_list_get_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "alicev@example.com", "alicev")
    hdr = _login(client, "alicev", "secret1234")

    r = client.post(
        p,
        headers=hdr,
        json={"title": "  My First Video ", "description": "desc", "tag_ids": []},
    )
    assert r.status_code == 201, r.text
    assert "no-store" in (r.headers.get("cache-control") or "").lower()
    body = r.json()
    vid = uuid.UUID(body["id"])
    assert body["status"] == "draft"
    assert body["title"] == "My First Video"
    assert body["author_id"]

    r_list = client.get(p)
    assert r_list.status_code == 200
    assert r_list.json() == []
    assert r_list.headers.get("X-Total-Count") == "0"

    ahdr = _admin(db_session, client)
    r_pub = _publish_via_review(client, p, vid, hdr, ahdr)
    assert r_pub.json().get("published_at") is not None

    r_anon = client.get(p + f"/{vid}")
    assert r_anon.status_code == 200
    assert "private" in (r_anon.headers.get("cache-control") or "").lower()
    assert "authorization" in (r_anon.headers.get("vary") or "").lower()

    r_list2 = client.get(p)
    assert len(r_list2.json()) == 1
    assert r_list2.headers.get("X-Total-Count") == "1"
    assert r_list2.headers.get("X-Has-More") == "false"
    assert "private" in (r_list2.headers.get("cache-control") or "").lower()

    assert "no-store" in (r_pub.headers.get("cache-control") or "").lower()  # approve POST


def test_draft_hidden_from_anonymous(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "bobv@example.com", "bobv")
    hdr = _login(client, "bobv", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "draft only", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    r2 = client.get(p + f"/{vid}")
    assert r2.status_code == 404


def test_admin_sees_draft_in_list(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "carol@example.com", "carol")
    uhdr = _login(client, "carol", "secret1234")
    r = client.post(p, headers=uhdr, json={"title": "adm list", "tag_ids": []})
    assert r.status_code == 201
    ahdr = _admin(db_session, client)
    r2 = client.get(p, headers=ahdr, params={"status": "draft"})
    assert r2.status_code == 200
    assert int(r2.headers.get("X-Total-Count", "0")) >= 1


def test_published_author_cannot_set_draft(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "dan@example.com", "dan")
    hdr = _login(client, "dan", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "pub", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    ahdr = _admin(db_session, client)
    _publish_via_review(client, p, vid, hdr, ahdr)
    r_bad = client.patch(p + f"/{vid}", headers=hdr, json={"status": "draft"})
    assert r_bad.status_code == 400


def test_published_author_can_offline(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "eve@example.com", "eve")
    hdr = _login(client, "eve", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "off", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    ahdr = _admin(db_session, client)
    _publish_via_review(client, p, vid, hdr, ahdr)
    r2 = client.patch(p + f"/{vid}", headers=hdr, json={"status": "offline"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "offline"


def test_platform_offline_hidden_from_anonymous_and_other_user(client, db_session):
    """管理员下架后：匿名与其余普通用户不可见；作者与管理员仍可 GET。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "offanon_a@example.com", "offanon_a")
    _register(client, "offanon_b@example.com", "offanon_b")
    hdr_a = _login(client, "offanon_a", "secret1234")
    hdr_b = _login(client, "offanon_b", "secret1234")
    ahdr = _admin(db_session, client)
    r = client.post(p, headers=hdr_a, json={"title": "offline visibility", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    _publish_via_review(client, p, vid, hdr_a, ahdr)
    assert client.get(p + f"/{vid}").status_code == 200
    ro = client.post(f"{p}/{vid}/offline", headers=ahdr)
    assert ro.status_code == 200
    assert ro.json()["status"] == "offline"
    assert client.get(p + f"/{vid}").status_code == 404
    assert client.get(p + f"/{vid}", headers=hdr_b).status_code == 404
    assert client.get(p + f"/{vid}", headers=hdr_a).status_code == 200
    assert client.get(p + f"/{vid}", headers=ahdr).status_code == 200


def test_non_author_patch_forbidden(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "frank@example.com", "frank")
    _register(client, "grace@example.com", "grace")
    h1 = _login(client, "frank", "secret1234")
    h2 = _login(client, "grace", "secret1234")
    r = client.post(p, headers=h1, json={"title": "mine", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    r2 = client.patch(p + f"/{vid}", headers=h2, json={"title": "hack"})
    assert r2.status_code == 403


def test_admin_get_draft_detail(client, db_session):
    """指标 4：管理员可查看任意状态视频详情。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "hank@example.com", "hank")
    uhdr = _login(client, "hank", "secret1234")
    r = client.post(p, headers=uhdr, json={"title": "adm draft view", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    ahdr = _admin(db_session, client)
    r2 = client.get(p + f"/{vid}", headers=ahdr)
    assert r2.status_code == 200
    assert r2.json()["status"] == "draft"


def test_author_get_own_draft_detail(client, db_session):
    """指标 4：作者本人可查看自己的 draft。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "ivy@example.com", "ivy")
    hdr = _login(client, "ivy", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "own draft", "tag_ids": []})
    vid = uuid.UUID(r.json()["id"])
    r2 = client.get(p + f"/{vid}", headers=hdr)
    assert r2.status_code == 200


def test_create_rejects_unknown_author_id_field(client, db_session):
    """创建体 extra=forbid：禁止携带 author_id 等未定义字段（422）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "jack@example.com", "jack")
    _register(client, "kate@example.com", "kate")
    h_jack = _login(client, "jack", "secret1234")
    h_kate = _login(client, "kate", "secret1234")
    r_k = client.get(f"{settings.API_V1_PREFIX}/users/me", headers=h_kate)
    kate_id = r_k.json()["id"]
    r = client.post(
        p,
        headers=h_jack,
        json={"title": "auth inject", "tag_ids": [], "author_id": kate_id},
    )
    assert r.status_code == 422, r.text


def test_create_with_category_and_tags_persisted(client, db_session):
    """指标 3：category / tag 关联正确保存。"""
    pv = f"{settings.API_V1_PREFIX}/videos"
    pc = f"{settings.API_V1_PREFIX}/categories"
    pt = f"{settings.API_V1_PREFIX}/tags"
    ahdr = _admin(db_session, client)
    cat = client.post(pc, headers=ahdr, json={"name": "vcat-1", "description": None})
    assert cat.status_code == 201
    cid = cat.json()["id"]
    tg = client.post(pt, headers=ahdr, json={"name": "vtag-1"})
    assert tg.status_code == 201
    tid = tg.json()["id"]
    _register(client, "leo@example.com", "leo")
    hdr = _login(client, "leo", "secret1234")
    r = client.post(
        pv,
        headers=hdr,
        json={"title": "tagged", "category_id": cid, "tag_ids": [tid]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category_id"] == cid
    assert len(body["tags"]) == 1
    assert body["tags"][0]["id"] == tid
    vid = body["id"]
    r2 = client.get(pv + f"/{vid}", headers=hdr)
    assert r2.json()["tags"][0]["name"] == "vtag-1"


def test_list_filter_category_tag_and_pagination(client, db_session):
    """指标 5：category / tag 筛选与分页。"""
    pv = f"{settings.API_V1_PREFIX}/videos"
    pc = f"{settings.API_V1_PREFIX}/categories"
    pt = f"{settings.API_V1_PREFIX}/tags"
    ahdr = _admin(db_session, client)
    cid = client.post(pc, headers=ahdr, json={"name": "flt-cat", "description": None}).json()["id"]
    tid = client.post(pt, headers=ahdr, json={"name": "flt-tag"}).json()["id"]
    _register(client, "mia@example.com", "mia")
    hdr = _login(client, "mia", "secret1234")
    vids = []
    for i in range(3):
        r0 = client.post(
            pv,
            headers=hdr,
            json={"title": f"pub{i}", "category_id": cid, "tag_ids": [tid]},
        )
        assert r0.status_code == 201
        vids.append(r0.json()["id"])
    for vid in vids:
        _publish_via_review(client, pv, vid, hdr, ahdr)
    r_cat = client.get(pv, params={"category_id": cid})
    assert r_cat.status_code == 200
    assert len(r_cat.json()) == 3
    r_tag = client.get(pv, params={"tag_id": tid})
    assert len(r_tag.json()) == 3
    assert int(r_tag.headers.get("X-Total-Count", "0")) == 3
    r_page = client.get(pv, params={"category_id": cid, "limit": 2, "offset": 0})
    assert len(r_page.json()) == 2
    assert int(r_page.headers.get("X-Total-Count", "0")) == 3
    r_page2 = client.get(pv, params={"category_id": cid, "limit": 2, "offset": 2})
    assert len(r_page2.json()) == 1


def test_admin_filter_non_published_statuses(client, db_session):
    """指标 5：管理员可按 draft / pending_review / rejected / offline 筛选。"""
    pv = f"{settings.API_V1_PREFIX}/videos"
    ahdr = _admin(db_session, client)
    _register(client, "noa@example.com", "noa")
    uhdr = _login(client, "noa", "secret1234")
    v1 = client.post(pv, headers=uhdr, json={"title": "st-pend", "tag_ids": []}).json()["id"]
    assert client.post(f"{pv}/{v1}/submit-review", headers=uhdr).status_code == 200
    v2 = client.post(pv, headers=uhdr, json={"title": "st-rej", "tag_ids": []}).json()["id"]
    assert client.post(f"{pv}/{v2}/submit-review", headers=uhdr).status_code == 200
    assert (
        client.post(
            f"{pv}/{v2}/reject",
            headers=ahdr,
            json={"rejection_reason": "不符合规范"},
        ).status_code
        == 200
    )
    v3 = client.post(pv, headers=uhdr, json={"title": "st-off", "tag_ids": []}).json()["id"]
    _publish_via_review(client, pv, v3, uhdr, ahdr)
    assert client.post(f"{pv}/{v3}/offline", headers=ahdr).status_code == 200
    for st in ("pending_review", "rejected", "offline"):
        r = client.get(pv, headers=ahdr, params={"status": st})
        assert r.status_code == 200
        assert int(r.headers.get("X-Total-Count", "0")) >= 1


def test_non_admin_cannot_use_status_query_param(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "pat@example.com", "pat")
    hdr = _login(client, "pat", "secret1234")
    r = client.get(p, headers=hdr, params={"status": "draft"})
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_STATUS_QUERY_FORBIDDEN


def test_video_list_keyset_cursor(client, db_session):
    pv = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "cursoru@example.com", "cursoru")
    hdr = _login(client, "cursoru", "secret1234")
    ahdr = _admin(db_session, client)
    titles = []
    for i in range(5):
        r = client.post(pv, headers=hdr, json={"title": f"ks{i}", "tag_ids": []})
        assert r.status_code == 201
        titles.append(r.json()["id"])
        _publish_via_review(client, pv, titles[-1], hdr, ahdr)
    r1 = client.get(pv, params={"limit": 2})
    assert r1.status_code == 200
    assert len(r1.json()) == 2
    assert r1.headers.get("X-Has-More") == "true"
    assert "X-Next-Cursor" in r1.headers
    cur = r1.headers["X-Next-Cursor"]
    r2 = client.get(pv, params={"limit": 2, "cursor": cur})
    assert len(r2.json()) == 2
    assert r2.headers.get("X-Has-More") == "true"
    r_bad = client.get(pv, params={"limit": 2, "cursor": cur, "offset": 1})
    assert r_bad.status_code == 400


def test_video_idempotency_post_replay(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "idem@example.com", "idem")
    hdr = _login(client, "idem", "secret1234")
    idem = {"Idempotency-Key": "idem-key-1"}
    body = {"title": "once", "tag_ids": []}
    r1 = client.post(p, headers={**hdr, **idem}, json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post(p, headers={**hdr, **idem}, json=body)
    assert r2.status_code == 201
    assert r2.json()["id"] == r1.json()["id"]


def test_video_idempotency_post_conflict(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "idem2@example.com", "idem2")
    hdr = _login(client, "idem2", "secret1234")
    idem = {"Idempotency-Key": "idem-key-2"}
    assert client.post(p, headers={**hdr, **idem}, json={"title": "a", "tag_ids": []}).status_code == 201
    r2 = client.post(p, headers={**hdr, **idem}, json={"title": "b", "tag_ids": []})
    assert r2.status_code == 409
    assert r2.json().get("code") == VIDEO_IDEMPOTENCY_CONFLICT


def test_video_idempotency_503_when_strict_no_redis(monkeypatch, client, db_session):
    from app.core import config
    from app.infrastructure import redis as redis_infra

    monkeypatch.setattr(config.settings, "IDEMPOTENCY_ALLOW_MEMORY_FALLBACK", False)
    monkeypatch.setattr(redis_infra, "redis_available_cached", lambda: False)

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "idem503@example.com", "idem503")
    hdr = _login(client, "idem503", "secret1234")
    r = client.post(
        p,
        headers={**hdr, "Idempotency-Key": "strict-no-redis"},
        json={"title": "x", "tag_ids": []},
    )
    assert r.status_code == 503
    assert r.json().get("code") == VIDEO_IDEMPOTENCY_BACKEND_UNAVAILABLE


def test_video_detail_etag_and_304(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "etaguser@example.com", "etaguser")
    hdr = _login(client, "etaguser", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "etag vid", "tag_ids": []})
    vid = r.json()["id"]
    ahdr = _admin(db_session, client)
    _publish_via_review(client, p, vid, hdr, ahdr)
    r1 = client.get(p + f"/{vid}")
    assert r1.status_code == 200
    etag = r1.headers.get("etag")
    assert etag and etag.startswith("W/")

    r304 = client.get(p + f"/{vid}", headers={"If-None-Match": etag})
    assert r304.status_code == 304
    assert r304.headers.get("etag") == etag

    client.patch(p + f"/{vid}", headers=hdr, json={"title": "changed"})
    r2 = client.get(p + f"/{vid}", headers={"If-None-Match": etag})
    assert r2.status_code == 200
    assert r2.headers.get("etag") != etag


def test_openapi_video_paths_and_responses(client, db_session):
    spec = openapi_skip_unless_exposed(client)
    prefix = settings.API_V1_PREFIX
    root = spec["paths"][f"{prefix}/videos"]
    assert root["get"]["summary"] == "视频列表"
    assert "400" in root["get"]["responses"]
    assert "200" in root["get"]["responses"]
    h200 = root["get"]["responses"]["200"].get("headers") or {}
    assert "X-Total-Count" in h200 or "x-total-count" in {k.lower(): k for k in h200}
    assert "X-Has-More" in h200 or "x-has-more" in {k.lower(): k for k in h200}
    qnames = [p["name"] for p in root["get"].get("parameters", [])]
    assert "cursor" in qnames

    detail_paths = [
        k
        for k in spec["paths"]
        if k.startswith(f"{prefix}/videos/")
        and "get" in spec["paths"][k]
        and k.count("/") == prefix.count("/") + 2
        and "{video_id}" in k
    ]
    vid_path = min(detail_paths, key=len)
    detail = spec["paths"][vid_path]["get"]
    assert "304" in detail["responses"]
    assert "404" in detail["responses"]
    assert root["post"]["responses"].get("422") is not None
    assert root["post"]["responses"].get("409") is not None
    assert root["post"]["responses"].get("503") is not None

    patch_key = f"{prefix}/videos/{{video_id}}"
    assert "409" in spec["paths"][patch_key]["patch"]["responses"]


def test_published_video_detail_counter_fields_match_database(client, db_session):
    """已发布详情中的 ``views_count`` / ``likes_count`` / ``favorites_count`` 与表列一致。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "cnt81@example.com", "cnt81")
    hdr = _login(client, "cnt81", "secret1234")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "cnt", "tag_ids": []}).json()["id"])
    _publish_via_review(client, p, vid, hdr, ahdr)
    j = client.get(p + f"/{vid}").json()
    row = db_session.execute(
        select(Video.views_count, Video.likes_count, Video.favorites_count).where(Video.id == vid)
    ).one()
    assert j["views_count"] == int(row[0])
    assert j["likes_count"] == int(row[1])
    assert j["favorites_count"] == int(row[2])


def test_pending_review_detail_author_json_matches_database(client, db_session):
    """待审稿：作者 GET 详情字段与 ``videos`` 行一致。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "pend81@example.com", "pend81")
    hdr = _login(client, "pend81", "secret1234")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "pend", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    j = client.get(p + f"/{vid}", headers=hdr).json()
    row = db_session.execute(
        select(Video.status, Video.title, Video.likes_count, Video.favorites_count, Video.views_count).where(
            Video.id == vid
        )
    ).one()
    assert j["status"] == row[0].value
    assert j["title"] == row[1]
    assert j["likes_count"] == int(row[2])
    assert j["favorites_count"] == int(row[3])
    assert j["views_count"] == int(row[4])


def test_video_response_shape_no_extra_secrets(client, db_session):
    """指标 7：响应不含用户敏感字段等。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "olga@example.com", "olga")
    hdr = _login(client, "olga", "secret1234")
    r = client.post(p, headers=hdr, json={"title": "shape", "tag_ids": []})
    body = r.json()
    forbidden = ("hashed_password", "email", "deleted_at", "is_active")
    for k in forbidden:
        assert k not in body
    assert "tags" in body
    assert isinstance(body["tags"], list)
    assert "rejection_reason" in body
    assert "row_version" in body
    assert isinstance(body["row_version"], int)
    assert body["row_version"] >= 1
