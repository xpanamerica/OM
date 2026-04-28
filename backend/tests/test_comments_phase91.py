"""阶段 9.1：评论模块最小测试（对齐验收指标 1–4）。

验收索引（最后把关时按项 grep / 跑本文件即可）：

1. **评论创建**
   - ``test_comment_crud_on_published_video`` — 登录用户评论 published 视频
   - ``test_comment_post_requires_auth`` — 未登录不能评论
   - ``test_comment_post_only_published`` — 作者对未发布视频不能发（``COMMENT_VIDEO_NOT_PUBLISHED``）
   - ``test_comment_post_stranger_cannot_comment_others_draft`` — 非作者普通用户对他人草稿不能发（404）

2. **评论列表**
   - ``test_gate91_published_anonymous_can_list_comments`` — published 匿名可列
   - ``test_gate91_soft_deleted_hidden_row_persists`` — 软删不展示、库内仍存
   - ``test_gate91_list_order_created_at_asc`` — 默认按创建时间升序
   - ``test_gate91_comment_list_etag_304_when_unchanged`` — ``ETag`` / ``If-None-Match`` → 304

3. **删除逻辑**
   - ``test_comment_crud_on_published_video`` / ``test_comment_delete_twice_not_found`` — 作者软删
   - ``test_comment_delete_admin_ok`` — 管理员可删
   - ``test_comment_delete_forbidden_other_user`` — 他人不可删
   - ``test_gate91_soft_deleted_hidden_row_persists`` — 软删非物理删

4. **数据库层**
   - ``test_gate91_foreign_key_video_cascade`` — ``comments.video_id`` → ``videos`` ON DELETE CASCADE
   - 迁移链：``alembic/versions/0015_comments_table.py``、``0016_comments_partial_list_index.py``；
     全链见 ``tests/test_alembic_sqlite.py`` / ``tests/test_user_module_completion_gate.py`` 中 upgrade head。

**限流与契约（补充）**
   - ``test_gate91_comment_post_503_when_strict_redis_backend_fails`` — Redis 严格模式 → 503
   - ``test_gate91_comment_post_rate_limit_429_and_retry_after`` — 429 + ``Retry-After``
   - ``test_openapi_includes_comment_paths`` — OpenAPI 含 429/503 等

5. **待审稿与鉴权（最后把关）**
   - ``test_comment_post_pending_review_requires_published`` — ``pending_review`` 仍不可评
   - ``test_comment_delete_requires_auth`` — 删除须登录
   - ``test_comment_list_author_pending_review_empty_200`` — 作者可看本人待审稿下评论列表（空）
   - ``test_comment_list_stranger_pending_review_video_not_found`` — 他人待审稿下列表 404
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select

from app.core.comment_codes import (
    COMMENT_FORBIDDEN,
    COMMENT_NOT_FOUND,
    COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE,
    COMMENT_RATE_LIMITED,
    COMMENT_VIDEO_NOT_PUBLISHED,
)
from app.core.comment_cursor import encode_comment_list_cursor
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_codes import VIDEO_NOT_FOUND
from app.models.comment import Comment
from app.models.enums import UserRole
from app.models.video import Video
from app.repositories import user_repository
from app.services import comment_service
from tests.support.openapi_contracts import collect_operation_tags, openapi_skip_unless_exposed


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
        email="adm91@example.com",
        username="adm91",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "adm91")


def _publish_video(client, db_session, hdr, ahdr) -> uuid.UUID:
    """创建草稿 → 提交审核 → 管理员通过，返回 video id。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "c91", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200
    return vid


def test_comment_crud_on_published_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91a@example.com", "c91a")
    hdr = _login(client, "c91a")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)

    r_post = client.post(
        f"{p}/{vid}/comments",
        headers=hdr,
        json={"content": "  第一条  "},
    )
    assert r_post.status_code == 200
    body = r_post.json()
    cid = uuid.UUID(body["id"])
    assert body["content"] == "第一条"
    assert body["video_id"] == str(vid)

    r_list = client.get(f"{p}/{vid}/comments")
    assert r_list.status_code == 200
    assert int(r_list.headers.get("X-Total-Count", "0")) == 1
    assert len(r_list.json()) == 1

    r_del = client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=hdr)
    assert r_del.status_code == 204

    r_list2 = client.get(f"{p}/{vid}/comments")
    assert r_list2.status_code == 200
    assert int(r_list2.headers.get("X-Total-Count", "-1")) == 0
    assert r_list2.json() == []


def test_comment_post_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91b@example.com", "c91b")
    hdr = _login(client, "c91b")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    r = client.post(f"{p}/{vid}/comments", json={"content": "x"})
    assert r.status_code == 401


def test_comment_delete_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91del401@example.com", "c91del401")
    hdr = _login(client, "c91del401")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "delme"}).json()["id"]
    )
    assert client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}").status_code == 401


def test_comment_post_only_published(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91c@example.com", "c91c")
    hdr = _login(client, "c91c")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "draft", "tag_ids": []}).json()["id"])
    r = client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "no"})
    assert r.status_code == 400
    assert r.json().get("code") == COMMENT_VIDEO_NOT_PUBLISHED


def test_comment_post_pending_review_requires_published(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91pr@example.com", "c91pr")
    hdr = _login(client, "c91pr")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "prc", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    r = client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "wait"})
    assert r.status_code == 400
    assert r.json().get("code") == COMMENT_VIDEO_NOT_PUBLISHED


def test_comment_post_stranger_cannot_comment_others_draft(client, db_session):
    """非作者普通用户：对他人未发布视频不可评论（无查看权 → 404）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91owner@example.com", "c91owner")
    _register(client, "c91stranger@example.com", "c91stranger")
    owner_hdr = _login(client, "c91owner")
    stranger_hdr = _login(client, "c91stranger")
    vid = uuid.UUID(client.post(p, headers=owner_hdr, json={"title": "draft2", "tag_ids": []}).json()["id"])
    r = client.post(f"{p}/{vid}/comments", headers=stranger_hdr, json={"content": "nope"})
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_comment_list_non_published_requires_viewer(client, db_session):
    """非发布视频：匿名 GET 评论列表 → 404；作者可拉取（空列表亦 200）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91d@example.com", "c91d")
    hdr = _login(client, "c91d")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "d", "tag_ids": []}).json()["id"])
    assert client.get(f"{p}/{vid}/comments").status_code == 404
    r = client.get(f"{p}/{vid}/comments", headers=hdr)
    assert r.status_code == 200
    assert r.json() == []


def test_comment_list_author_pending_review_empty_200(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91prl@example.com", "c91prl")
    hdr = _login(client, "c91prl")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "prlist", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    r = client.get(f"{p}/{vid}/comments", headers=hdr)
    assert r.status_code == 200
    assert r.json() == []


def test_comment_list_stranger_pending_review_video_not_found(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91pro@example.com", "c91pro")
    _register(client, "c91prs@example.com", "c91prs")
    ho = _login(client, "c91pro")
    hs = _login(client, "c91prs")
    vid = uuid.UUID(client.post(p, headers=ho, json={"title": "prhide", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=ho).status_code == 200
    r = client.get(f"{p}/{vid}/comments", headers=hs)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_comment_delete_forbidden_other_user(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91e@example.com", "c91e")
    _register(client, "c91f@example.com", "c91f")
    h1 = _login(client, "c91e")
    h2 = _login(client, "c91f")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, h1, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=h1, json={"content": "mine"}).json()["id"]
    )
    r = client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=h2)
    assert r.status_code == 403
    assert r.json().get("code") == COMMENT_FORBIDDEN


def test_comment_delete_admin_ok(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91g@example.com", "c91g")
    hdr = _login(client, "c91g")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "x"}).json()["id"]
    )
    assert client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=ahdr).status_code == 204


def test_comment_delete_twice_not_found(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91h@example.com", "c91h")
    hdr = _login(client, "c91h")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "x"}).json()["id"]
    )
    assert client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=hdr).status_code == 204
    r2 = client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=hdr)
    assert r2.status_code == 404
    assert r2.json().get("code") == COMMENT_NOT_FOUND


def test_comment_unknown_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c91i@example.com", "c91i")
    hdr = _login(client, "c91i")
    bad = uuid.uuid4()
    r = client.post(f"{p}/{bad}/comments", headers=hdr, json={"content": "x"})
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_gate91_comment_list_etag_304_when_unchanged(client, db_session):
    """列表支持 If-None-Match：未改时 304 且无 JSON 正文。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "etagc91@example.com", "etagc91")
    hdr = _login(client, "etagc91")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "e1"}).status_code == 200
    r1 = client.get(f"{p}/{vid}/comments")
    assert r1.status_code == 200
    etag = r1.headers.get("etag") or r1.headers.get("ETag")
    assert etag and etag.startswith("W/")
    r304 = client.get(f"{p}/{vid}/comments", headers={"If-None-Match": etag})
    assert r304.status_code == 304
    assert r304.content == b""
    assert int(r304.headers.get("X-Total-Count", "0")) == 1


def test_gate91_published_anonymous_can_list_comments(client, db_session):
    """指标 2：已发布视频匿名可拉取评论列表。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91a@example.com", "gate91a")
    hdr = _login(client, "gate91a")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "hello"}).status_code == 200
    r = client.get(f"{p}/{vid}/comments")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["content"] == "hello"


def test_gate91_comment_list_cursor_pagination(client, db_session):
    """游标分页：``X-Next-Cursor`` 与 ``cursor`` 参数衔接多页。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "cur91@example.com", "cur91")
    hdr = _login(client, "cur91")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    for i in range(5):
        assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": f"m{i}"}).status_code == 200
    r1 = client.get(f"{p}/{vid}/comments", params={"limit": 2})
    assert r1.status_code == 200
    assert int(r1.headers["X-Total-Count"]) == 5
    assert len(r1.json()) == 2
    assert r1.headers.get("X-Next-Cursor")
    c2 = r1.headers["X-Next-Cursor"]
    r2 = client.get(f"{p}/{vid}/comments", params={"limit": 2, "cursor": c2})
    assert r2.status_code == 200
    assert len(r2.json()) == 2
    assert int(r2.headers["X-Total-Count"]) == 5
    c3 = r2.headers.get("X-Next-Cursor")
    assert c3
    r3 = client.get(f"{p}/{vid}/comments", params={"limit": 2, "cursor": c3})
    assert r3.status_code == 200
    assert len(r3.json()) == 1
    assert not r3.headers.get("X-Next-Cursor")


def test_gate91_comment_list_cursor_offset_mutex(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "mux91@example.com", "mux91")
    hdr = _login(client, "mux91")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "one"}).status_code == 200
    bad_cursor = encode_comment_list_cursor(comment_id=uuid.uuid4())
    r = client.get(f"{p}/{vid}/comments", params={"limit": 10, "offset": 1, "cursor": bad_cursor})
    assert r.status_code == 400


def test_gate91_comment_list_cursor_invalid(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "badc91@example.com", "badc91")
    hdr = _login(client, "badc91")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    r = client.get(f"{p}/{vid}/comments", params={"cursor": "not-valid-cursor"})
    assert r.status_code == 400


def test_gate91_list_order_created_at_asc(client, db_session):
    """指标 2：默认按创建时间升序。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91b@example.com", "gate91b")
    hdr = _login(client, "gate91b")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "first"}).status_code == 200
    time.sleep(0.02)
    assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "second"}).status_code == 200
    rows = client.get(f"{p}/{vid}/comments").json()
    assert [x["content"] for x in rows] == ["first", "second"]


def test_gate91_soft_deleted_hidden_row_persists(client, db_session):
    """指标 2–3：列表不展示已软删；库内行仍存在且 is_deleted。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91c@example.com", "gate91c")
    hdr = _login(client, "gate91c")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "secret body"}).json()["id"]
    )
    assert client.delete(f"{settings.API_V1_PREFIX}/comments/{cid}", headers=hdr).status_code == 204
    assert client.get(f"{p}/{vid}/comments").json() == []

    row = db_session.get(Comment, cid)
    assert row is not None
    assert row.is_deleted is True
    assert row.content == "secret body"


def test_gate91_x_total_count_with_pagination(client, db_session):
    """列表 ``X-Total-Count`` 为未软删总数，与 ``limit`` 无关。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91e@example.com", "gate91e")
    hdr = _login(client, "gate91e")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    for i in range(3):
        assert client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": f"c{i}"}).status_code == 200
    r = client.get(f"{p}/{vid}/comments", params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    assert int(r.headers["X-Total-Count"]) == 3
    assert len(r.json()) == 2


def test_gate91_admin_can_list_comments_on_author_draft(client, db_session):
    """非发布视频：管理员可拉取评论列表（与 ``can_view_video`` 一致）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91f@example.com", "gate91f")
    hdr = _login(client, "gate91f")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "dr", "tag_ids": []}).json()["id"])
    r = client.get(f"{p}/{vid}/comments", headers=ahdr)
    assert r.status_code == 200
    assert int(r.headers.get("X-Total-Count", "-1")) == 0


def test_openapi_includes_comment_paths(client, db_session):
    spec = openapi_skip_unless_exposed(client)
    prefix = settings.API_V1_PREFIX
    assert "comments" in collect_operation_tags(spec["paths"])
    post_key = f"{prefix}/videos/{{video_id}}/comments"
    assert post_key in spec["paths"]
    assert "post" in spec["paths"][post_key]
    r429 = spec["paths"][post_key]["post"].get("responses", {}).get("429", {})
    assert r429
    h429 = r429.get("headers") or {}
    assert "Retry-After" in h429 or "retry-after" in {x.lower(): x for x in h429}
    assert "503" in spec["paths"][post_key]["post"].get("responses", {})
    get_key = post_key
    assert "get" in spec["paths"][get_key]
    assert "400" in spec["paths"][get_key]["get"].get("responses", {})
    assert "304" in spec["paths"][get_key]["get"].get("responses", {})
    h200 = spec["paths"][get_key]["get"]["responses"].get("200", {}).get("headers") or {}
    assert "X-Total-Count" in h200 or "x-total-count" in {x.lower(): x for x in h200}
    assert "X-Next-Cursor" in h200 or "x-next-cursor" in {x.lower(): x for x in h200}
    del_key = f"{prefix}/comments/{{comment_id}}"
    assert del_key in spec["paths"]
    assert "delete" in spec["paths"][del_key]


def test_gate91_comment_post_503_when_strict_redis_backend_fails(client, db_session, monkeypatch):
    """``COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=false`` 且 Redis 路径失败时 → 503 + 业务码。"""
    from app.core.comment_rate_limit import CommentRateLimitBackendError

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "rl503@example.com", "rl503")
    hdr = _login(client, "rl503")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)

    def _boom(*_a, **_k):
        raise CommentRateLimitBackendError("redis unavailable")

    monkeypatch.setattr(
        comment_service,
        "settings",
        settings.model_copy(update={"COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE": 5}),
    )
    monkeypatch.setattr(comment_service, "consume_comment_post_slot", _boom)
    r = client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "x"})
    assert r.status_code == 503
    assert r.json().get("code") == COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE


def test_gate91_comment_post_rate_limit_429_and_retry_after(client, db_session, monkeypatch):
    """限流开启时：同一用户同一视频第三次 POST 返回 429，且带 ``Retry-After`` 与业务 ``code``。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "rl91@example.com", "rl91")
    hdr = _login(client, "rl91")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    monkeypatch.setattr(
        comment_service,
        "settings",
        settings.model_copy(update={"COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE": 2}),
    )
    url = f"{p}/{vid}/comments"
    assert client.post(url, headers=hdr, json={"content": "a"}).status_code == 200
    assert client.post(url, headers=hdr, json={"content": "b"}).status_code == 200
    r3 = client.post(url, headers=hdr, json={"content": "c"})
    assert r3.status_code == 429
    assert r3.json().get("code") == COMMENT_RATE_LIMITED
    ra = r3.headers.get("Retry-After") or r3.headers.get("retry-after")
    assert ra is not None and int(ra) >= 1


def test_gate91_foreign_key_video_cascade(client, db_session):
    """指标 4：video_id 外键 ON DELETE CASCADE，删视频则评论物理消失。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate91d@example.com", "gate91d")
    hdr = _login(client, "gate91d")
    ahdr = _admin(db_session, client)
    vid = _publish_video(client, db_session, hdr, ahdr)
    cid = uuid.UUID(
        client.post(f"{p}/{vid}/comments", headers=hdr, json={"content": "x"}).json()["id"]
    )
    v = db_session.get(Video, vid)
    assert v is not None
    db_session.delete(v)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Comment, cid) is None
    assert db_session.scalar(select(Comment.id).where(Comment.id == cid)) is None
