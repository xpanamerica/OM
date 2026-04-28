"""阶段 14：概念节点、视频—概念绑定、学习路径。"""

from __future__ import annotations

from app.core.config import settings
from app.core.knowledge_codes import (
    CONCEPT_NAME_CONFLICT,
    CONCEPT_NOT_FOUND,
    LEARNING_PATH_FORBIDDEN,
    LEARNING_PATH_NOT_FOUND,
    LEARNING_PATH_PUBLISH_REQUIRES_PUBLISHED_VIDEOS,
)
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.repositories import user_repository


def _p() -> str:
    return settings.API_V1_PREFIX


def _reg(client, u: str, e: str):
    assert client.post(f"{_p()}/auth/register", json={"email": e, "username": u, "password": "secret1234"}).status_code == 201


def _login(client, u: str):
    r = client.post(f"{_p()}/auth/login", data={"username": u, "password": "secret1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin_hdr(db_session, client):
    user_repository.create_user(
        db_session,
        email="k14adm@example.com",
        username="k14adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "k14adm")


def _publish(client, p: str, vid: str, author: dict, admin: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=author).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=admin).status_code == 200


def test_admin_crud_concept_and_list(client, db_session):
    cp = f"{_p()}/concepts"
    adm = _admin_hdr(db_session, client)

    r1 = client.post(cp, headers=adm, json={"name": "Rust 所有权", "description": "核心概念"})
    assert r1.status_code == 201
    cid = r1.json()["id"]

    r_dup = client.post(cp, headers=adm, json={"name": "rust 所有权", "description": None})
    assert r_dup.status_code == 409
    assert r_dup.json().get("code") == CONCEPT_NAME_CONFLICT

    r_patch = client.patch(cp + f"/{cid}", headers=adm, json={"description": "更新说明"})
    assert r_patch.status_code == 200
    assert r_patch.json()["description"] == "更新说明"

    r_list = client.get(cp, params={"limit": 10, "offset": 0})
    assert r_list.status_code == 200
    assert int(r_list.headers.get("X-Total-Count", "0")) >= 1
    assert any(x["id"] == cid for x in r_list.json())


def test_admin_put_video_concepts_user_reads(client, db_session):
    vp = f"{_p()}/videos"
    cp = f"{_p()}/concepts"
    _reg(client, "k14u1", "k14u1@example.com")
    ah = _login(client, "k14u1")
    adm = _admin_hdr(db_session, client)

    c1 = client.post(cp, headers=adm, json={"name": "Lambda", "description": None}).json()["id"]
    c2 = client.post(cp, headers=adm, json={"name": "Closure", "description": None}).json()["id"]

    rv = client.post(vp, headers=ah, json={"title": "fn talk", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    put = client.put(
        f"{vp}/{vid}/concepts",
        headers=adm,
        json={
            "items": [
                {"concept_id": c1, "start_time_seconds": 0, "end_time_seconds": 60},
                {"concept_id": c2},
            ]
        },
    )
    assert put.status_code == 204

    r_anon = client.get(f"{vp}/{vid}/concepts")
    assert r_anon.status_code == 200
    body = r_anon.json()
    assert len(body) == 2
    names = {x["concept_name"] for x in body}
    assert names == {"Lambda", "Closure"}


def test_learning_path_create_publish_list_detail(client, db_session):
    vp = f"{_p()}/videos"
    lp = f"{_p()}/learning-paths"
    _reg(client, "k14u2", "k14u2@example.com")
    ah = _login(client, "k14u2")
    adm = _admin_hdr(db_session, client)

    r1 = client.post(vp, headers=ah, json={"title": "lesson A", "tag_ids": []})
    v1 = r1.json()["id"]
    r2 = client.post(vp, headers=ah, json={"title": "lesson B", "tag_ids": []})
    v2 = r2.json()["id"]
    _publish(client, vp, v1, ah, adm)
    _publish(client, vp, v2, ah, adm)

    rc = client.post(
        lp,
        headers=ah,
        json={
            "title": "入门两课",
            "description": "顺序学习",
            "is_published": False,
            "items": [
                {"video_id": v1, "order_index": 0, "note": "先看"},
                {"video_id": v2, "order_index": 1},
            ],
        },
    )
    assert rc.status_code == 201
    path_id = rc.json()["id"]
    assert rc.json()["is_published"] is False

    r_anon_list = client.get(lp)
    assert r_anon_list.status_code == 200
    assert path_id not in {x["id"] for x in r_anon_list.json()}

    r_pub = client.patch(lp + f"/{path_id}", headers=ah, json={"is_published": True})
    assert r_pub.status_code == 200

    r_anon_list2 = client.get(lp)
    assert path_id in {x["id"] for x in r_anon_list2.json()}

    r_detail = client.get(lp + f"/{path_id}")
    assert r_detail.status_code == 200
    assert len(r_detail.json()["items"]) == 2
    it0, it1 = r_detail.json()["items"][0], r_detail.json()["items"][1]
    assert it0["order_index"] == 0 and it1["order_index"] == 1
    assert it0["video_id"] == v1 and it1["video_id"] == v2
    assert it0["video"] is not None and it1["video"] is not None


def test_concept_reused_by_two_published_videos(client, db_session):
    """同一概念可绑定到多个视频（多对多一侧：概念复用）。"""
    vp = f"{_p()}/videos"
    cp = f"{_p()}/concepts"
    _reg(client, "k14reuse", "k14reuse@example.com")
    ah = _login(client, "k14reuse")
    adm = _admin_hdr(db_session, client)

    cid = client.post(cp, headers=adm, json={"name": "Idempotency", "description": None}).json()["id"]

    rv_a = client.post(vp, headers=ah, json={"title": "video A reuse", "tag_ids": []})
    rv_b = client.post(vp, headers=ah, json={"title": "video B reuse", "tag_ids": []})
    vid_a, vid_b = rv_a.json()["id"], rv_b.json()["id"]
    _publish(client, vp, vid_a, ah, adm)
    _publish(client, vp, vid_b, ah, adm)

    for vid in (vid_a, vid_b):
        r_put = client.put(f"{vp}/{vid}/concepts", headers=adm, json={"items": [{"concept_id": cid}]})
        assert r_put.status_code == 204
        r_get = client.get(f"{vp}/{vid}/concepts")
        assert r_get.status_code == 200
        rows = r_get.json()
        assert len(rows) == 1
        assert rows[0]["concept_id"] == cid
        assert rows[0]["concept_name"] == "Idempotency"


def test_other_logged_in_user_cannot_get_unpublished_path_detail(client, db_session):
    """未发布路径：非作者、非管理员的登录用户与匿名一样不可见详情。"""
    lp = f"{_p()}/learning-paths"
    _reg(client, "k14own", "k14own@example.com")
    _reg(client, "k14peer", "k14peer@example.com")
    h_own = _login(client, "k14own")
    h_peer = _login(client, "k14peer")

    path_id = client.post(lp, headers=h_own, json={"title": "owner draft", "is_published": False}).json()["id"]

    r_peer = client.get(lp + f"/{path_id}", headers=h_peer)
    assert r_peer.status_code == 404
    assert r_peer.json().get("code") == LEARNING_PATH_NOT_FOUND


def test_publish_path_rejects_non_published_video(client, db_session):
    vp = f"{_p()}/videos"
    lp = f"{_p()}/learning-paths"
    _reg(client, "k14u3", "k14u3@example.com")
    ah = _login(client, "k14u3")
    adm = _admin_hdr(db_session, client)

    r_pubv = client.post(vp, headers=ah, json={"title": "pub only", "tag_ids": []})
    pub_id = r_pubv.json()["id"]
    _publish(client, vp, pub_id, ah, adm)

    r_draft = client.post(vp, headers=ah, json={"title": "draft only", "tag_ids": []})
    draft_id = r_draft.json()["id"]

    rc = client.post(
        lp,
        headers=ah,
        json={
            "title": "bad mix",
            "is_published": True,
            "items": [
                {"video_id": pub_id, "order_index": 0},
                {"video_id": draft_id, "order_index": 1},
            ],
        },
    )
    assert rc.status_code == 400
    assert rc.json().get("code") == LEARNING_PATH_PUBLISH_REQUIRES_PUBLISHED_VIDEOS


def test_non_owner_cannot_patch_path(client, db_session):
    vp = f"{_p()}/videos"
    lp = f"{_p()}/learning-paths"
    _reg(client, "k14u4a", "k14u4a@example.com")
    _reg(client, "k14u4b", "k14u4b@example.com")
    ha = _login(client, "k14u4a")
    hb = _login(client, "k14u4b")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ha, json={"title": "solo", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ha, adm)

    path_id = client.post(lp, headers=ha, json={"title": "mine", "items": [{"video_id": vid, "order_index": 0}]}).json()[
        "id"
    ]

    r_forbidden = client.patch(lp + f"/{path_id}", headers=hb, json={"title": "hijack"})
    assert r_forbidden.status_code == 403
    assert r_forbidden.json().get("code") == LEARNING_PATH_FORBIDDEN


def test_anon_cannot_see_unpublished_path_detail(client, db_session):
    lp = f"{_p()}/learning-paths"
    _reg(client, "k14u5", "k14u5@example.com")
    ah = _login(client, "k14u5")

    path_id = client.post(lp, headers=ah, json={"title": "draft path", "is_published": False}).json()["id"]

    r404 = client.get(lp + f"/{path_id}")
    assert r404.status_code == 404
    assert r404.json().get("code") == LEARNING_PATH_NOT_FOUND


def test_concept_linked_videos_lists_published_with_segments(client, db_session):
    """GET /concepts/{id}/videos：已发布绑定、X-Total-Count、片段时间字段。"""
    vp = f"{_p()}/videos"
    cp = f"{_p()}/concepts"
    _reg(client, "k14cv", "k14cv@example.com")
    ah = _login(client, "k14cv")
    adm = _admin_hdr(db_session, client)

    c1 = client.post(cp, headers=adm, json={"name": "SegmentConcept", "description": None}).json()["id"]
    rv = client.post(vp, headers=ah, json={"title": "segment clip", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    assert (
        client.put(
            f"{vp}/{vid}/concepts",
            headers=adm,
            json={"items": [{"concept_id": c1, "start_time_seconds": 10, "end_time_seconds": 120}]},
        ).status_code
        == 204
    )

    r = client.get(f"{cp}/{c1}/videos", params={"offset": 0, "limit": 20})
    assert r.status_code == 200
    assert int(r.headers.get("X-Total-Count", "0")) == 1
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == vid
    assert body[0]["title"] == "segment clip"
    assert body[0]["status"] == "published"
    assert body[0]["start_time_seconds"] == 10
    assert body[0]["end_time_seconds"] == 120

    bad = "00000000-0000-0000-0000-000000000099"
    r404 = client.get(f"{cp}/{bad}/videos")
    assert r404.status_code == 404
    assert r404.json().get("code") == CONCEPT_NOT_FOUND
