"""阶段 8.2：视频审核与状态流转最小测试。"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_codes import (
    VIDEO_APPROVE_FORBIDDEN,
    VIDEO_APPROVE_INVALID_STATE,
    VIDEO_CONFLICT_OPTIMISTIC,
    VIDEO_LIST_CURSOR_OFFSET_CONFLICT,
    VIDEO_LIST_INVALID_CURSOR,
    VIDEO_NOT_FOUND,
    VIDEO_OFFLINE_FORBIDDEN,
    VIDEO_OFFLINE_INVALID_STATE,
    VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT,
    VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT,
    VIDEO_REJECT_FORBIDDEN,
    VIDEO_REJECT_INVALID_STATE,
    VIDEO_SUBMIT_FORBIDDEN,
    VIDEO_SUBMIT_INVALID_STATE,
    VIDEO_WORKFLOW_EVENTS_FORBIDDEN,
)
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.models.enums import UserRole
from app.models.video import Video
from app.models.video_workflow_event import VideoWorkflowEvent
from app.repositories import user_repository, video_workflow_event_repository
from tests.support.openapi_contracts import openapi_skip_unless_exposed


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
        email="adm82@example.com",
        username="adm82",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "adm82")


def test_workflow_writes_audit_events(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "audit82@example.com", "audit82")
    hdr = _login(client, "audit82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "aud1", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200

    rows = db_session.scalars(
        select(VideoWorkflowEvent)
        .where(VideoWorkflowEvent.video_id == vid)
        .order_by(VideoWorkflowEvent.created_at, VideoWorkflowEvent.audit_sequence)
    ).all()
    assert len(rows) == 2
    assert rows[0].action == video_workflow_event_repository.ACTION_SUBMIT_REVIEW
    assert rows[0].from_status == "draft"
    assert rows[0].to_status == "pending_review"
    assert rows[1].action == video_workflow_event_repository.ACTION_APPROVE
    assert rows[1].from_status == "pending_review"
    assert rows[1].to_status == "published"


def test_submit_review_draft_to_pending_author(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "a82@example.com", "a82")
    hdr = _login(client, "a82")
    vid = client.post(p, headers=hdr, json={"title": "s1", "tag_ids": []}).json()["id"]
    r = client.post(f"{p}/{vid}/submit-review", headers=hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"
    assert r.json().get("rejection_reason") is None


def test_submit_review_admin_can_submit_others_draft(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "b82@example.com", "b82")
    uhdr = _login(client, "b82")
    vid = client.post(p, headers=uhdr, json={"title": "s2", "tag_ids": []}).json()["id"]
    ahdr = _admin(db_session, client)
    r = client.post(f"{p}/{vid}/submit-review", headers=ahdr)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"


def test_submit_review_forbidden_non_author(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "c82@example.com", "c82")
    _register(client, "d82@example.com", "d82")
    h1 = _login(client, "c82")
    h2 = _login(client, "d82")
    vid = client.post(p, headers=h1, json={"title": "s3", "tag_ids": []}).json()["id"]
    r = client.post(f"{p}/{vid}/submit-review", headers=h2)
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_SUBMIT_FORBIDDEN


def test_submit_review_invalid_not_draft(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "e82@example.com", "e82")
    hdr = _login(client, "e82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "s4", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    r2 = client.post(f"{p}/{vid}/submit-review", headers=hdr)
    assert r2.status_code == 400
    assert r2.json().get("code") == VIDEO_SUBMIT_INVALID_STATE


def test_approve_and_reject_and_offline(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "f82@example.com", "f82")
    hdr = _login(client, "f82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "ap1", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    ra = client.post(f"{p}/{vid}/approve", headers=ahdr)
    assert ra.status_code == 200
    assert ra.json()["status"] == "published"
    assert ra.json().get("published_at") is not None

    vid2 = client.post(p, headers=hdr, json={"title": "rj1", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid2}/submit-review", headers=hdr)
    rr = client.post(
        f"{p}/{vid2}/reject",
        headers=ahdr,
        json={"rejection_reason": "  内容不合规  "},
    )
    assert rr.status_code == 200
    assert rr.json()["status"] == "rejected"
    assert rr.json()["rejection_reason"] == "内容不合规"

    vid3 = client.post(p, headers=hdr, json={"title": "of1", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid3}/submit-review", headers=hdr)
    client.post(f"{p}/{vid3}/approve", headers=ahdr)
    ro = client.post(f"{p}/{vid3}/offline", headers=ahdr)
    assert ro.status_code == 200
    assert ro.json()["status"] == "offline"


def test_approve_forbidden_non_admin(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "g82@example.com", "g82")
    hdr = _login(client, "g82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "apx", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    r = client.post(f"{p}/{vid}/approve", headers=hdr)
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_APPROVE_FORBIDDEN


def test_approve_invalid_not_pending(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "h82@example.com", "h82")
    hdr = _login(client, "h82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "apy", "tag_ids": []}).json()["id"]
    r = client.post(f"{p}/{vid}/approve", headers=ahdr)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_APPROVE_INVALID_STATE


def test_reject_invalid_not_pending(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    ahdr = _admin(db_session, client)
    _register(client, "i82@example.com", "i82")
    hdr = _login(client, "i82")
    vid = uuid.uuid4()
    r = client.post(
        f"{p}/{vid}/reject",
        headers=ahdr,
        json={"rejection_reason": "x"},
    )
    assert r.status_code == 404
    vid2 = client.post(p, headers=hdr, json={"title": "rj2", "tag_ids": []}).json()["id"]
    r2 = client.post(
        f"{p}/{vid2}/reject",
        headers=ahdr,
        json={"rejection_reason": "x"},
    )
    assert r2.status_code == 400
    assert r2.json().get("code") == VIDEO_REJECT_INVALID_STATE


def test_offline_forbidden_non_admin(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "j82@example.com", "j82")
    hdr = _login(client, "j82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "ofx", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.post(f"{p}/{vid}/offline", headers=hdr)
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_OFFLINE_FORBIDDEN


def test_offline_invalid_not_published(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    ahdr = _admin(db_session, client)
    _register(client, "k82@example.com", "k82")
    hdr = _login(client, "k82")
    vid = client.post(p, headers=hdr, json={"title": "ofy", "tag_ids": []}).json()["id"]
    r = client.post(f"{p}/{vid}/offline", headers=ahdr)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_OFFLINE_INVALID_STATE


def test_patch_status_must_use_dedicated_endpoints(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "m82@example.com", "m82")
    hdr = _login(client, "m82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "px1", "tag_ids": []}).json()["id"]
    r = client.patch(p + f"/{vid}", headers=hdr, json={"status": "pending_review"})
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT

    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    r2 = client.patch(p + f"/{vid}", headers=ahdr, json={"status": "published"})
    assert r2.status_code == 400
    assert r2.json().get("code") == VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT


def test_admin_patch_offline_must_use_post_offline(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "n82@example.com", "n82")
    hdr = _login(client, "n82")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "px2", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.patch(p + f"/{vid}", headers=ahdr, json={"status": "offline"})
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT


def test_reject_forbidden_non_admin(client, db_session):
    """指标 2：普通用户（作者）不能驳回。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "rj403@example.com", "rj403")
    hdr = _login(client, "rj403")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "rj403v", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    r = client.post(
        f"{p}/{vid}/reject",
        headers=hdr,
        json={"rejection_reason": "作者不能驳回"},
    )
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_REJECT_FORBIDDEN


def test_workflow_post_illegal_transitions_after_publish_or_offline(client, db_session):
    """指标 1 拒绝项（经 POST）：已发布不可再提交审核；已发布不可驳回；已下架不可再通过审核；已下架不可再提交审核。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "postbad@example.com", "postbad")
    hdr = _login(client, "postbad")
    ahdr = _admin(db_session, client)

    vp = client.post(p, headers=hdr, json={"title": "pub", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vp}/submit-review", headers=hdr)
    client.post(f"{p}/{vp}/approve", headers=ahdr)
    r_pub_submit = client.post(f"{p}/{vp}/submit-review", headers=hdr)
    assert r_pub_submit.status_code == 400
    assert r_pub_submit.json().get("code") == VIDEO_SUBMIT_INVALID_STATE
    r_pub_reject = client.post(
        f"{p}/{vp}/reject",
        headers=ahdr,
        json={"rejection_reason": "不应发生"},
    )
    assert r_pub_reject.status_code == 400
    assert r_pub_reject.json().get("code") == VIDEO_REJECT_INVALID_STATE

    vo = client.post(p, headers=hdr, json={"title": "off", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vo}/submit-review", headers=hdr)
    client.post(f"{p}/{vo}/approve", headers=ahdr)
    client.post(f"{p}/{vo}/offline", headers=ahdr)
    r_off_approve = client.post(f"{p}/{vo}/approve", headers=ahdr)
    assert r_off_approve.status_code == 400
    assert r_off_approve.json().get("code") == VIDEO_APPROVE_INVALID_STATE
    r_off_submit = client.post(f"{p}/{vo}/submit-review", headers=hdr)
    assert r_off_submit.status_code == 400
    assert r_off_submit.json().get("code") == VIDEO_SUBMIT_INVALID_STATE


def test_illegal_patch_transitions_rejected(client, db_session):
    """指标 1 拒绝项：draft→published / draft→rejected / published→pending_review 等不得经 PATCH 达成。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate1@example.com", "gate1")
    hdr = _login(client, "gate1")
    ahdr = _admin(db_session, client)
    v0 = client.post(p, headers=hdr, json={"title": "g0", "tag_ids": []}).json()["id"]
    assert client.patch(p + f"/{v0}", headers=hdr, json={"status": "published"}).status_code == 400
    assert client.patch(p + f"/{v0}", headers=hdr, json={"status": "rejected"}).status_code == 400
    assert client.patch(p + f"/{v0}", headers=ahdr, json={"status": "published"}).status_code == 400

    v1 = client.post(p, headers=hdr, json={"title": "g1", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{v1}/submit-review", headers=hdr)
    client.post(f"{p}/{v1}/approve", headers=ahdr)
    assert client.patch(p + f"/{v1}", headers=hdr, json={"status": "pending_review"}).status_code == 400

    v2 = client.post(p, headers=hdr, json={"title": "g2", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{v2}/submit-review", headers=hdr)
    client.post(f"{p}/{v2}/approve", headers=ahdr)
    client.post(f"{p}/{v2}/offline", headers=ahdr)
    assert client.patch(p + f"/{v2}", headers=ahdr, json={"status": "published"}).status_code == 400


def test_workflow_posts_return_404_when_video_missing(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate404@example.com", "gate404")
    ahdr = _admin(db_session, client)
    bad = uuid.uuid4()
    assert client.post(f"{p}/{bad}/submit-review", headers=ahdr).status_code == 404
    assert client.post(f"{p}/{bad}/approve", headers=ahdr).status_code == 404
    assert client.post(f"{p}/{bad}/offline", headers=ahdr).status_code == 404
    rj = client.post(
        f"{p}/{bad}/reject",
        headers=ahdr,
        json={"rejection_reason": "nope"},
    )
    assert rj.status_code == 404


def test_submit_review_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate401@example.com", "gate401")
    hdr = _login(client, "gate401")
    vid = client.post(p, headers=hdr, json={"title": "g401", "tag_ids": []}).json()["id"]
    assert client.post(f"{p}/{vid}/submit-review").status_code == 401


def test_workflow_approve_reject_offline_require_auth(client, db_session):
    """管理员专属 POST：未带 Token 时一律 401。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wf401a@example.com", "wf401a")
    hdr = _login(client, "wf401a")
    ahdr = _admin(db_session, client)
    v1 = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf401-1", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{v1}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{v1}/approve").status_code == 401

    v2 = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf401-2", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{v2}/submit-review", headers=hdr).status_code == 200
    assert (
        client.post(
            f"{p}/{v2}/reject",
            json={"rejection_reason": "x"},
        ).status_code
        == 401
    )

    v3 = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf401-3", "tag_ids": []}).json()["id"])
    assert client.post(f"{p}/{v3}/submit-review", headers=hdr).status_code == 200
    assert client.post(f"{p}/{v3}/approve", headers=ahdr).status_code == 200
    assert client.post(f"{p}/{v3}/offline").status_code == 401


def test_reject_does_not_set_published_at_submit_clears_rejection_reason(client, db_session):
    """指标 3、4：驳回不写 published_at；再次提交清除驳回说明。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "gate34@example.com", "gate34")
    hdr = _login(client, "gate34")
    ahdr = _admin(db_session, client)
    vid = client.post(p, headers=hdr, json={"title": "g34", "tag_ids": []}).json()["id"]
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    rr = client.post(
        f"{p}/{vid}/reject",
        headers=ahdr,
        json={"rejection_reason": "第一次驳回"},
    )
    assert rr.status_code == 200
    assert rr.json().get("published_at") is None
    assert rr.json()["rejection_reason"] == "第一次驳回"

    r_draft = client.patch(p + f"/{vid}", headers=ahdr, json={"status": "draft"})
    assert r_draft.status_code == 200
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    r_pending = client.get(f"{p}/{vid}", headers=hdr)
    assert r_pending.status_code == 200
    assert r_pending.json().get("rejection_reason") is None
    assert r_pending.json().get("published_at") is None


def test_openapi_includes_workflow_post_paths(client, db_session):
    """指标 6：OpenAPI 出现四个审核相关 POST。"""
    spec = openapi_skip_unless_exposed(client)
    prefix = settings.API_V1_PREFIX
    suffixes = (
        "/submit-review",
        "/approve",
        "/reject",
        "/offline",
    )
    found = [k for k in spec["paths"] if k.startswith(f"{prefix}/videos/") and any(k.endswith(s) for s in suffixes)]
    for s in suffixes:
        assert any(k.endswith(s) for k in found), f"missing path ending {s}"
        path_key = next(k for k in found if k.endswith(s))
        assert f"{prefix}/videos/{{video_id}}{s}" == path_key or "video_id" in path_key
        assert "post" in spec["paths"][path_key]

    ev_key = next(k for k in spec["paths"] if k.endswith("/workflow-events"))
    assert "get" in spec["paths"][ev_key]
    assert "200" in spec["paths"][ev_key]["get"]["responses"]
    h200 = spec["paths"][ev_key]["get"]["responses"]["200"].get("headers") or {}
    assert "X-Total-Count" in h200 or "x-total-count" in {x.lower(): x for x in h200}
    qn = [p["name"] for p in spec["paths"][ev_key]["get"].get("parameters", [])]
    assert "cursor" in qn and "offset" in qn and "limit" in qn


def test_admin_list_workflow_events(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfev82@example.com", "wfev82")
    hdr = _login(client, "wfev82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf1", "tag_ids": []}).json()["id"])
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.get(f"{p}/{vid}/workflow-events", headers=ahdr)
    assert r.status_code == 200
    assert int(r.headers.get("X-Total-Count", "0")) >= 2
    data = r.json()
    assert len(data) >= 2
    assert {x["action"] for x in data} >= {"submit_review", "approve"}


def test_workflow_events_author_sees_own_even_without_events(client, db_session):
    """作者可拉取本人视频审计列表（空列表亦 200）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfa82@example.com", "wfa82")
    hdr = _login(client, "wfa82")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf-own", "tag_ids": []}).json()["id"])
    r = client.get(f"{p}/{vid}/workflow-events", headers=hdr)
    assert r.status_code == 200
    assert r.json() == []
    assert int(r.headers.get("X-Total-Count", "-1")) == 0


def test_workflow_events_non_owner_on_published_forbidden(client, db_session):
    """已发布视频：非作者非管理员不可看审计（403，与详情可见性分离）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfoa82@example.com", "wfoa82")
    _register(client, "wfob82@example.com", "wfob82")
    ha = _login(client, "wfoa82")
    hb = _login(client, "wfob82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "wf-pub", "tag_ids": []}).json()["id"])
    client.post(f"{p}/{vid}/submit-review", headers=ha)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.get(f"{p}/{vid}/workflow-events", headers=hb)
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_WORKFLOW_EVENTS_FORBIDDEN


def test_workflow_events_requires_auth(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfe401@example.com", "wfe401")
    hdr = _login(client, "wfe401")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "wf401", "tag_ids": []}).json()["id"])
    assert client.get(f"{p}/{vid}/workflow-events").status_code == 401


def test_workflow_events_other_user_draft_not_visible(client, db_session):
    """他人草稿：与详情一致统一 404。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfd82a@example.com", "wfd82a")
    _register(client, "wfd82b@example.com", "wfd82b")
    ha = _login(client, "wfd82a")
    hb = _login(client, "wfd82b")
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "secret draft", "tag_ids": []}).json()["id"])
    r = client.get(f"{p}/{vid}/workflow-events", headers=hb)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_optimistic_lock_row_version_two_sessions(client, db_session):
    """双会话并发写同一行：第二提交触发 StaleDataError（SQLAlchemy 乐观锁）。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "opt82@example.com", "opt82")
    hdr = _login(client, "opt82")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "opt1", "tag_ids": []}).json()["id"])

    factory = sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)
    sa = factory()
    sb = factory()
    try:
        va = sa.get(Video, vid)
        vb = sb.get(Video, vid)
        assert va is not None and vb is not None
        va.title = va.title + "A"
        sa.commit()
        vb.title = vb.title + "B"
        with pytest.raises(StaleDataError):
            sb.commit()
    finally:
        sa.close()
        sb.close()


def test_workflow_events_cursor_pagination(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfcur82@example.com", "wfcur82")
    hdr = _login(client, "wfcur82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "cur", "tag_ids": []}).json()["id"])
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    client.post(f"{p}/{vid}/offline", headers=ahdr)

    r1 = client.get(f"{p}/{vid}/workflow-events", headers=ahdr, params={"limit": 1})
    assert r1.status_code == 200
    assert int(r1.headers["X-Total-Count"]) >= 3
    assert r1.headers.get("X-Has-More") == "true"
    cur = r1.headers.get("X-Next-Cursor")
    assert cur

    r2 = client.get(f"{p}/{vid}/workflow-events", headers=ahdr, params={"limit": 1, "cursor": cur})
    assert r2.status_code == 200
    assert r2.json()[0]["id"] != r1.json()[0]["id"]


def test_workflow_events_cursor_offset_conflict(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfco82@example.com", "wfco82")
    hdr = _login(client, "wfco82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "co", "tag_ids": []}).json()["id"])
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.get(
        f"{p}/{vid}/workflow-events",
        headers=ahdr,
        params={"limit": 10, "offset": 1, "cursor": "bogus"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_LIST_CURSOR_OFFSET_CONFLICT


def test_workflow_events_invalid_cursor(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "wfic82@example.com", "wfic82")
    hdr = _login(client, "wfic82")
    ahdr = _admin(db_session, client)
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "ic", "tag_ids": []}).json()["id"])
    client.post(f"{p}/{vid}/submit-review", headers=hdr)
    client.post(f"{p}/{vid}/approve", headers=ahdr)
    r = client.get(
        f"{p}/{vid}/workflow-events",
        headers=ahdr,
        params={"limit": 5, "cursor": "not-a-valid-cursor!!!"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_LIST_INVALID_CURSOR


def test_stale_data_error_maps_to_409_json():
    """全局异常处理：StaleDataError → 409 + VIDEO_CONFLICT_OPTIMISTIC。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise StaleDataError("concurrent", None, None)

    r = TestClient(app).get("/boom")
    assert r.status_code == 409
    assert r.json().get("code") == VIDEO_CONFLICT_OPTIMISTIC
