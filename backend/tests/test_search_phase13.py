"""阶段 13：搜索、最新、热门（数据库级）。"""

from __future__ import annotations

import uuid

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_codes import (
    VIDEO_CATEGORY_NOT_FOUND,
    VIDEO_SEARCH_KEYWORD_TOO_LONG,
    VIDEO_SEARCH_RATE_LIMITED,
    VIDEO_TAG_NOT_FOUND,
)
from app.models.enums import UserRole, VideoStatus
from app.models.video import Video
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
        email="s13adm@example.com",
        username="s13adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "s13adm")


def _publish(client, p: str, vid: str, author: dict, admin: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=author).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=admin).status_code == 200


def test_search_keyword_title_and_description(client, db_session):
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    _reg(client, "s13u1", "s13u1@example.com")
    ah = _login(client, "s13u1")
    adm = _admin_hdr(db_session, client)

    r = client.post(p, headers=ah, json={"title": "Alpha uniqueX13", "description": "no match", "tag_ids": []})
    v1 = r.json()["id"]
    r2 = client.post(p, headers=ah, json={"title": "Other", "description": "has uniqueX13 in body", "tag_ids": []})
    v2 = r2.json()["id"]
    _publish(client, p, v1, ah, adm)
    _publish(client, p, v2, ah, adm)

    r_hit = client.get(sp, params={"keyword": "uniqueX13"})
    assert r_hit.status_code == 200
    ids = {x["id"] for x in r_hit.json()}
    assert v1 in ids and v2 in ids
    assert int(r_hit.headers.get("X-Total-Count", "0")) >= 2


def test_search_category_and_tag_and_sort_views(client, db_session):
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    cp = f"{_p()}/categories"
    tp = f"{_p()}/tags"
    _reg(client, "s13u2", "s13u2@example.com")
    ah = _login(client, "s13u2")
    adm = _admin_hdr(db_session, client)

    cat_id = client.post(cp, headers=adm, json={"name": "CatS13", "list_order": 1}).json()["id"]
    tag_id = client.post(tp, headers=adm, json={"name": "TagS13", "list_order": 1}).json()["id"]

    r1 = client.post(
        p,
        headers=ah,
        json={"title": "Low views", "tag_ids": [tag_id], "category_id": cat_id},
    )
    v1 = uuid.UUID(r1.json()["id"])
    r2 = client.post(
        p,
        headers=ah,
        json={"title": "High views", "tag_ids": [tag_id], "category_id": cat_id},
    )
    v2 = uuid.UUID(r2.json()["id"])
    _publish(client, p, str(v1), ah, adm)
    _publish(client, p, str(v2), ah, adm)

    db_session.execute(update(Video).where(Video.id == v1).values(views_count=1))
    db_session.execute(update(Video).where(Video.id == v2).values(views_count=999))
    db_session.commit()

    r_cat = client.get(sp, params={"category_id": str(cat_id), "sort_by": "latest"})
    assert r_cat.status_code == 200
    assert all(x["category_id"] == cat_id for x in r_cat.json())

    r_tag = client.get(sp, params={"tag_id": str(tag_id), "sort_by": "views"})
    assert r_tag.status_code == 200
    body = r_tag.json()
    assert body[0]["id"] == str(v2)
    assert body[0]["views_count"] >= body[-1]["views_count"]


def test_search_non_admin_only_published(client, db_session):
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    _reg(client, "s13u3", "s13u3@example.com")
    ah = _login(client, "s13u3")
    adm = _admin_hdr(db_session, client)

    r = client.post(p, headers=ah, json={"title": "draftonly s13kw", "tag_ids": []})
    draft_id = r.json()["id"]
    r2 = client.post(p, headers=ah, json={"title": "pub s13kw", "tag_ids": []})
    pub_id = r2.json()["id"]
    _publish(client, p, pub_id, ah, adm)

    r_anon = client.get(sp, params={"keyword": "s13kw"})
    assert r_anon.status_code == 200
    ids = {x["id"] for x in r_anon.json()}
    assert pub_id in ids
    assert draft_id not in ids

    r_adm = client.get(sp, params={"keyword": "s13kw"}, headers=adm)
    assert r_adm.status_code == 200
    ids2 = {x["id"] for x in r_adm.json()}
    assert draft_id in ids2 and pub_id in ids2


def test_search_non_admin_excludes_offline_after_platform_offline(client, db_session):
    """已发布再被平台下架：匿名/普通用户搜索命中 published 过滤，管理员仍可搜到 offline。"""
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    kw = "s13offZ9unique"
    _reg(client, "s13offu", "s13offu@example.com")
    ah = _login(client, "s13offu")
    adm = _admin_hdr(db_session, client)

    r_pub = client.post(p, headers=ah, json={"title": f"live {kw}", "tag_ids": []})
    vid = r_pub.json()["id"]
    _publish(client, p, vid, ah, adm)

    r_seen = client.get(sp, params={"keyword": kw})
    assert r_seen.status_code == 200
    assert vid in {x["id"] for x in r_seen.json()}

    assert client.post(f"{p}/{vid}/offline", headers=adm).status_code == 200

    r_anon = client.get(sp, params={"keyword": kw})
    assert r_anon.status_code == 200
    assert vid not in {x["id"] for x in r_anon.json()}

    r_adm = client.get(sp, params={"keyword": kw}, headers=adm)
    assert r_adm.status_code == 200
    assert vid in {x["id"] for x in r_adm.json()}
    hit = next(x for x in r_adm.json() if x["id"] == vid)
    assert hit["status"] == VideoStatus.OFFLINE.value


def test_search_pagination_latest_keyword_total_and_offsets(client, db_session):
    """``offset``/``limit`` 与 ``X-Total-Count`` 同源；``sort_by=latest`` 下翻页顺序稳定。"""
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    kw = "s13pagUnique"
    _reg(client, "s13page", "s13page@example.com")
    ah = _login(client, "s13page")
    adm = _admin_hdr(db_session, client)

    titles = (f"a {kw}", f"b {kw}", f"c {kw}")
    ids: list[uuid.UUID] = []
    for t in titles:
        r = client.post(p, headers=ah, json={"title": t, "tag_ids": []})
        ids.append(uuid.UUID(r.json()["id"]))
    for vid in ids:
        _publish(client, p, str(vid), ah, adm)

    v_a, v_b, v_c = ids
    now = datetime.now(timezone.utc)
    db_session.execute(update(Video).where(Video.id == v_a).values(created_at=now - timedelta(days=3)))
    db_session.execute(update(Video).where(Video.id == v_b).values(created_at=now - timedelta(days=2)))
    db_session.execute(update(Video).where(Video.id == v_c).values(created_at=now - timedelta(hours=1)))
    db_session.commit()

    params_base = {"keyword": kw, "sort_by": "latest", "limit": 1}
    r0 = client.get(sp, params={**params_base, "offset": 0})
    r1 = client.get(sp, params={**params_base, "offset": 1})
    r2 = client.get(sp, params={**params_base, "offset": 2})
    assert r0.status_code == r1.status_code == r2.status_code == 200
    total = int(r0.headers.get("X-Total-Count", "-1"))
    assert total == 3
    assert int(r1.headers.get("X-Total-Count", "-1")) == 3
    assert int(r2.headers.get("X-Total-Count", "-1")) == 3
    assert len(r0.json()) == len(r1.json()) == len(r2.json()) == 1
    assert r0.json()[0]["id"] == str(v_c)
    assert r1.json()[0]["id"] == str(v_b)
    assert r2.json()[0]["id"] == str(v_a)


def test_search_unknown_category_and_tag(client, db_session):
    sp = f"{_p()}/search/videos"
    adm = _admin_hdr(db_session, client)
    bad = str(uuid.uuid4())
    r = client.get(sp, params={"category_id": bad}, headers=adm)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_CATEGORY_NOT_FOUND
    r2 = client.get(sp, params={"tag_id": bad}, headers=adm)
    assert r2.status_code == 400
    assert r2.json().get("code") == VIDEO_TAG_NOT_FOUND


def test_latest_and_trending_only_published_order(client, db_session):
    p = f"{_p()}/videos"
    lp = f"{_p()}/videos/latest"
    tr = f"{_p()}/videos/trending"
    _reg(client, "s13u4", "s13u4@example.com")
    ah = _login(client, "s13u4")
    adm = _admin_hdr(db_session, client)

    r_old = client.post(p, headers=ah, json={"title": "older pub", "tag_ids": []})
    v_old = uuid.UUID(r_old.json()["id"])
    _publish(client, p, str(v_old), ah, adm)

    r_new = client.post(p, headers=ah, json={"title": "newer pub", "tag_ids": []})
    v_new = uuid.UUID(r_new.json()["id"])
    _publish(client, p, str(v_new), ah, adm)

    r_d = client.post(p, headers=ah, json={"title": "never pub", "tag_ids": []})
    draft_only = uuid.UUID(r_d.json()["id"])
    _ = draft_only

    now = datetime.now(timezone.utc)
    db_session.execute(update(Video).where(Video.id == v_old).values(created_at=now - timedelta(days=2)))
    db_session.execute(update(Video).where(Video.id == v_new).values(created_at=now - timedelta(hours=1)))
    db_session.execute(
        update(Video)
        .where(Video.id == v_old)
        .values(views_count=1000, likes_count=0, favorites_count=0)
    )
    db_session.execute(
        update(Video)
        .where(Video.id == v_new)
        .values(views_count=0, likes_count=500, favorites_count=0)
    )
    db_session.commit()

    r_l = client.get(lp, params={"limit": 10, "offset": 0})
    assert r_l.status_code == 200
    assert r_l.json()[0]["id"] == str(v_new)
    assert int(r_l.headers.get("X-Total-Count", "0")) >= 2
    assert all(x["status"] == "published" for x in r_l.json())

    r_t = client.get(tr, params={"limit": 10, "offset": 0})
    assert r_t.status_code == 200
    # v_new score = 500*4 = 2000, v_old = 1000*1 = 1000
    assert r_t.json()[0]["id"] == str(v_new)
    assert int(r_t.headers.get("X-Total-Count", "0")) >= 2
    assert all(x["status"] == VideoStatus.PUBLISHED.value for x in r_t.json())


def test_latest_path_not_shadowed_by_uuid_route(client, db_session):
    """``/videos/latest`` 须命中列表路由，而非将 ``latest`` 解析为 UUID。"""
    r = client.get(f"{_p()}/videos/latest", params={"limit": 1})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_search_keyword_exceeds_config_max_returns_400(client, db_session, monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(update={"VIDEO_SEARCH_KEYWORD_MAX_LENGTH": 6}),
    )
    sp = f"{_p()}/search/videos"
    adm = _admin_hdr(db_session, client)
    r = client.get(sp, params={"keyword": "1234567"}, headers=adm)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_SEARCH_KEYWORD_TOO_LONG


def test_trending_order_follows_configurable_weights(client, db_session, monkeypatch):
    """运营调权：提高点赞系数后，高赞低播应排在高播低赞之前。"""
    import app.core.config as cfg

    p = f"{_p()}/videos"
    tr = f"{_p()}/videos/trending"
    _reg(client, "s13trw", "s13trw@example.com")
    ah = _login(client, "s13trw")
    adm = _admin_hdr(db_session, client)

    r1 = client.post(p, headers=ah, json={"title": "high views trw", "tag_ids": []})
    v1 = uuid.UUID(r1.json()["id"])
    r2 = client.post(p, headers=ah, json={"title": "high likes trw", "tag_ids": []})
    v2 = uuid.UUID(r2.json()["id"])
    _publish(client, p, str(v1), ah, adm)
    _publish(client, p, str(v2), ah, adm)

    db_session.execute(update(Video).where(Video.id == v1).values(views_count=10_000, likes_count=0))
    db_session.execute(update(Video).where(Video.id == v2).values(views_count=0, likes_count=60))
    db_session.commit()

    r0 = client.get(tr, params={"limit": 5})
    assert r0.status_code == 200
    assert r0.json()[0]["id"] == str(v1)

    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(
            update={
                "VIDEO_TRENDING_WEIGHT_VIEWS": 1,
                "VIDEO_TRENDING_WEIGHT_LIKES": 250,
                "VIDEO_TRENDING_WEIGHT_FAVORITES": 1,
            }
        ),
    )
    r1b = client.get(tr, params={"limit": 5})
    assert r1b.status_code == 200
    assert r1b.json()[0]["id"] == str(v2)


def test_search_videos_rate_limit_429(client, db_session, monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(update={"VIDEO_SEARCH_MAX_REQUESTS_PER_MINUTE": 2}),
    )
    _ = _admin_hdr(db_session, client)
    sp = f"{_p()}/search/videos"
    assert client.get(sp).status_code == 200
    assert client.get(sp).status_code == 200
    r3 = client.get(sp)
    assert r3.status_code == 429
    assert r3.json().get("code") == VIDEO_SEARCH_RATE_LIMITED
    assert r3.headers.get("Retry-After") == "60"


def test_trending_recency_half_life_can_boost_newer_over_higher_base_score(client, db_session, monkeypatch):
    """``VIDEO_TRENDING_RECENCY_HALF_LIFE_DAYS``>0 时，较新稿件的有效分可超过更旧的高分稿。"""
    import app.core.config as cfg

    p = f"{_p()}/videos"
    tr = f"{_p()}/videos/trending"
    _reg(client, "s13rec", "s13rec@example.com")
    ah = _login(client, "s13rec")
    adm = _admin_hdr(db_session, client)

    r_old = client.post(p, headers=ah, json={"title": "old high views", "tag_ids": []})
    v_old = uuid.UUID(r_old.json()["id"])
    r_new = client.post(p, headers=ah, json={"title": "new lower views", "tag_ids": []})
    v_new = uuid.UUID(r_new.json()["id"])
    _publish(client, p, str(v_old), ah, adm)
    _publish(client, p, str(v_new), ah, adm)

    now = datetime.now(timezone.utc)
    db_session.execute(
        update(Video)
        .where(Video.id == v_old)
        .values(views_count=5000, likes_count=0, favorites_count=0, published_at=now - timedelta(days=90))
    )
    db_session.execute(
        update(Video)
        .where(Video.id == v_new)
        .values(views_count=2000, likes_count=0, favorites_count=0, published_at=now - timedelta(hours=1))
    )
    db_session.commit()

    r_no_decay = client.get(tr, params={"limit": 10})
    assert r_no_decay.status_code == 200
    assert r_no_decay.json()[0]["id"] == str(v_old)

    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(update={"VIDEO_TRENDING_RECENCY_HALF_LIFE_DAYS": 30.0}),
    )
    r_decay = client.get(tr, params={"limit": 10})
    assert r_decay.status_code == 200
    assert r_decay.json()[0]["id"] == str(v_new)


def test_search_sort_likes(client, db_session):
    p = f"{_p()}/videos"
    sp = f"{_p()}/search/videos"
    _reg(client, "s13u5", "s13u5@example.com")
    ah = _login(client, "s13u5")
    adm = _admin_hdr(db_session, client)

    r1 = client.post(p, headers=ah, json={"title": "likeA s13lk", "tag_ids": []})
    u1 = uuid.UUID(r1.json()["id"])
    r2 = client.post(p, headers=ah, json={"title": "likeB s13lk", "tag_ids": []})
    u2 = uuid.UUID(r2.json()["id"])
    _publish(client, p, str(u1), ah, adm)
    _publish(client, p, str(u2), ah, adm)
    db_session.execute(update(Video).where(Video.id == u1).values(likes_count=1))
    db_session.execute(update(Video).where(Video.id == u2).values(likes_count=99))
    db_session.commit()

    r = client.get(sp, params={"keyword": "s13lk", "sort_by": "likes"})
    assert r.status_code == 200
    assert r.json()[0]["id"] == str(u2)
