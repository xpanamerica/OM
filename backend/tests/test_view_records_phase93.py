"""阶段 9.3：播放记录最小测试。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.view_record_codes import (
    VIEW_RECORD_CURSOR_INVALID,
    VIEW_RECORD_CURSOR_WITH_OFFSET,
    VIEW_RECORD_LAST_VIEWED_IN_FUTURE,
    VIEW_RECORD_REQUIRES_PUBLISHED,
)
from app.infrastructure.observability.view_record_metrics import (
    inc_view_record_contended_insert_merge,
    inc_view_record_upsert,
    render_view_record_metrics_prometheus_text,
    reset_view_record_metrics_for_tests,
)
from app.models.enums import UserRole
from app.models.user import User
from app.models.video import Video
from app.models.view_record import ViewRecord
from app.repositories import user_repository
from app.schemas.view_record import ViewRecordUpsertIn
from app.services import view_record_service
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
        email="vr93adm@example.com",
        username="vr93adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "vr93adm")


def _publish(client, p: str, vid: uuid.UUID, hdr: dict, ahdr: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200


def test_first_view_record_increments_views_count_second_does_not(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93a@example.com", "vr93a")
    hdr = _login(client, "vr93a")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "v", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)

    assert client.get(f"{p}/{vid}").json()["views_count"] == 0

    r1 = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 10})
    assert r1.status_code == 200, r1.text
    assert r1.json()["progress_seconds"] == 10
    assert client.get(f"{p}/{vid}").json()["views_count"] == 1

    r2 = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 99})
    assert r2.status_code == 200
    assert r2.json()["progress_seconds"] == 99
    assert client.get(f"{p}/{vid}").json()["views_count"] == 1

    uid = db_session.execute(select(ViewRecord.user_id).where(ViewRecord.video_id == vid).limit(1)).scalar_one()
    n = db_session.scalar(select(func.count()).select_from(ViewRecord).where(ViewRecord.user_id == uid, ViewRecord.video_id == vid))
    assert n == 1


def test_view_record_draft_returns_400(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93b@example.com", "vr93b")
    hdr = _login(client, "vr93b")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "d", "tag_ids": []}).json()["id"])
    r = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 1})
    assert r.status_code == 400
    assert r.json().get("code") == VIEW_RECORD_REQUIRES_PUBLISHED


def test_view_record_pending_review_returns_400(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93pr@example.com", "vr93pr")
    hdr = _login(client, "vr93pr")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "prv", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    r = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 1})
    assert r.status_code == 400
    assert r.json().get("code") == VIEW_RECORD_REQUIRES_PUBLISHED


def test_view_record_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93c@example.com", "vr93c")
    hdr = _login(client, "vr93c")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "c", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/view-record", json={"progress_seconds": 1}).status_code == 401


def test_list_my_view_records(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    me = f"{settings.API_V1_PREFIX}/users/me/view-records"
    _register(client, "vr93d@example.com", "vr93d")
    hdr = _login(client, "vr93d")
    ahdr = _admin(db_session, client)
    v1 = uuid.UUID(client.post(p, headers=hdr, json={"title": "a", "tag_ids": []}).json()["id"])
    v2 = uuid.UUID(client.post(p, headers=hdr, json={"title": "b", "tag_ids": []}).json()["id"])
    _publish(client, p, v1, hdr, ahdr)
    _publish(client, p, v2, hdr, ahdr)

    now = datetime.now(timezone.utc)
    t1 = now - timedelta(days=2)
    t2 = now - timedelta(days=1)
    assert client.post(f"{p}/{v1}/view-record", headers=hdr, json={"progress_seconds": 1, "last_viewed_at": t1.isoformat()}).status_code == 200
    assert client.post(f"{p}/{v2}/view-record", headers=hdr, json={"progress_seconds": 2, "last_viewed_at": t2.isoformat()}).status_code == 200

    r = client.get(me, headers=hdr)
    assert r.status_code == 200
    assert r.headers.get("X-Total-Count") == "2"
    assert r.headers.get("X-Has-More") == "false"
    body = r.json()
    assert len(body) == 2
    assert body[0]["video_id"] == str(v2)
    assert body[1]["video_id"] == str(v1)
    assert body[0]["video_title"] == "b"
    assert body[1]["video_title"] == "a"


def test_list_view_records_requires_auth(client, db_session):
    assert client.get(f"{settings.API_V1_PREFIX}/users/me/view-records").status_code == 401


def test_list_my_view_records_excludes_other_users(client, db_session):
    """``GET /users/me/view-records`` 只返回当前用户记录，不含他人。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    me = f"{settings.API_V1_PREFIX}/users/me/view-records"
    _register(client, "vr93iso1@example.com", "vr93iso1")
    _register(client, "vr93iso2@example.com", "vr93iso2")
    h1 = _login(client, "vr93iso1")
    h2 = _login(client, "vr93iso2")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=h1, json={"title": "isoone", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, h1, ahdr)
    assert client.post(f"{p}/{vid}/view-record", headers=h1, json={"progress_seconds": 7}).status_code == 200
    r_owner = client.get(me, headers=h1)
    assert r_owner.status_code == 200
    assert r_owner.headers.get("X-Total-Count") == "1"
    r_other = client.get(me, headers=h2)
    assert r_other.status_code == 200
    assert r_other.headers.get("X-Total-Count") == "0"
    assert r_other.json() == []


def test_views_count_http_matches_video_table(client, db_session):
    """``GET /videos/{id}`` 的 ``views_count`` 与 ``videos.views_count`` 列一致。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93dbc@example.com", "vr93dbc")
    hdr = _login(client, "vr93dbc")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "dbvc", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    assert client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 1}).status_code == 200
    assert client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 2}).status_code == 200
    j = client.get(f"{p}/{vid}", headers=hdr).json()
    vc = db_session.scalar(select(Video.views_count).where(Video.id == vid))
    assert j["views_count"] == int(vc or 0) == 1


def test_last_viewed_at_naive_iso_normalized_to_utc(client, db_session):
    """客户端传无时区 ISO 时视为 UTC，避免 SQLite 等与 aware 混用歧义。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93e@example.com", "vr93e")
    hdr = _login(client, "vr93e")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "e", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    r = client.post(
        f"{p}/{vid}/view-record",
        headers=hdr,
        json={"progress_seconds": 3, "last_viewed_at": "2020-06-15T08:30:00"},
    )
    assert r.status_code == 200, r.text
    raw = r.json()["last_viewed_at"]
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert dt.tzinfo is not None
    assert dt.year == 2020 and dt.month == 6 and dt.day == 15
    assert dt.hour == 8 and dt.minute == 30


def test_two_users_first_view_each_increment_views_count(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93u1@example.com", "vr93u1")
    _register(client, "vr93u2@example.com", "vr93u2")
    h1 = _login(client, "vr93u1")
    h2 = _login(client, "vr93u2")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=h1, json={"title": "shared", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, h1, ahdr)
    assert client.post(f"{p}/{vid}/view-record", headers=h1, json={"progress_seconds": 1}).status_code == 200
    assert client.post(f"{p}/{vid}/view-record", headers=h2, json={"progress_seconds": 2}).status_code == 200
    assert client.get(f"{p}/{vid}").json()["views_count"] == 2


def test_future_last_viewed_at_rejected(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93fut@example.com", "vr93fut")
    hdr = _login(client, "vr93fut")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "fut", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    far = (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()
    r = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 1, "last_viewed_at": far})
    assert r.status_code == 400
    assert r.json().get("code") == VIEW_RECORD_LAST_VIEWED_IN_FUTURE


def test_cursor_with_offset_returns_400(client, db_session):
    me = f"{settings.API_V1_PREFIX}/users/me/view-records"
    _register(client, "vr93co@example.com", "vr93co")
    hdr = _login(client, "vr93co")
    r = client.get(me, headers=hdr, params={"cursor": "x", "offset": 1})
    assert r.status_code == 400
    assert r.json().get("code") == VIEW_RECORD_CURSOR_WITH_OFFSET


def test_invalid_cursor_returns_400(client, db_session):
    me = f"{settings.API_V1_PREFIX}/users/me/view-records"
    _register(client, "vr93ci@example.com", "vr93ci")
    hdr = _login(client, "vr93ci")
    r = client.get(me, headers=hdr, params={"cursor": "not-a-valid-token"})
    assert r.status_code == 400
    assert r.json().get("code") == VIEW_RECORD_CURSOR_INVALID


def test_cursor_pagination_second_page(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    me = f"{settings.API_V1_PREFIX}/users/me/view-records"
    _register(client, "vr93pg@example.com", "vr93pg")
    hdr = _login(client, "vr93pg")
    ahdr = _admin(db_session, client)
    ids = []
    for i in range(3):
        vid = uuid.UUID(client.post(p, headers=hdr, json={"title": f"p{i}", "tag_ids": []}).json()["id"])
        _publish(client, p, vid, hdr, ahdr)
        ids.append(vid)
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    for i, vid in enumerate(ids):
        assert (
            client.post(
                f"{p}/{vid}/view-record",
                headers=hdr,
                json={"progress_seconds": i, "last_viewed_at": (t0 + timedelta(hours=i)).isoformat()},
            ).status_code
            == 200
        )
    r1 = client.get(me, headers=hdr, params={"limit": 2})
    assert r1.status_code == 200
    assert r1.headers.get("X-Total-Count") == "3"
    assert r1.headers.get("X-Has-More") == "true"
    nc = r1.headers.get("X-Next-Cursor")
    assert nc
    r2 = client.get(me, headers=hdr, params={"limit": 2, "cursor": nc})
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.headers.get("X-Has-More") == "false"


def test_progress_seconds_above_max_returns_422(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93mx@example.com", "vr93mx")
    hdr = _login(client, "vr93mx")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "mx", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    r = client.post(f"{p}/{vid}/view-record", headers=hdr, json={"progress_seconds": 86_400 * 366 * 100 + 1})
    assert r.status_code == 422


def test_concurrent_first_upsert_single_row_and_views_count(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vr93mt@example.com", "vr93mt")
    hdr = _login(client, "vr93mt")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "mt", "tag_ids": []}).json()["id"])
    _publish(client, p, vid, hdr, ahdr)
    uid = db_session.scalar(select(User.id).where(User.username == "vr93mt"))
    assert uid is not None

    sf = sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def work() -> None:
        s = sf()
        try:
            u = s.get(User, uid)
            assert u is not None
            barrier.wait()
            view_record_service.upsert_view_record(s, u, vid, ViewRecordUpsertIn(progress_seconds=1))
        except BaseException as e:
            errors.append(e)
        finally:
            s.close()

    threads = (threading.Thread(target=work), threading.Thread(target=work))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    assert client.get(f"{p}/{vid}").json()["views_count"] == 1
    n = db_session.scalar(select(func.count()).select_from(ViewRecord).where(ViewRecord.user_id == uid, ViewRecord.video_id == vid))
    assert n == 1


def test_view_record_metrics_render_contains_counters():
    reset_view_record_metrics_for_tests()
    inc_view_record_upsert()
    inc_view_record_contended_insert_merge()
    body = render_view_record_metrics_prometheus_text().decode()
    assert "app_view_record_upsert_total" in body
    assert "app_view_record_contended_insert_merge_total" in body


def test_openapi_contains_view_record_routes_when_exposed(client):
    spec = openapi_skip_unless_exposed(client)
    paths = spec.get("paths") or {}
    prefix = settings.API_V1_PREFIX
    assert_openapi_paths(
        paths,
        f"{prefix}/videos/{{video_id}}/view-record",
        f"{prefix}/users/me/view-records",
    )
    assert "view-records" in collect_operation_tags(paths)
