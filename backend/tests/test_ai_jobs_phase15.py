"""阶段 15：AI 任务框架（Mock 执行器）。"""

from __future__ import annotations

import time

from app.core.ai_codes import AI_JOB_CREATE_FORBIDDEN, AI_JOB_NOT_FOUND
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import AiJobStatus, UserRole
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
        email="p15adm@example.com",
        username="p15adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "p15adm")


def _publish(client, p: str, vid: str, author: dict, admin: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=author).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=admin).status_code == 200


def _wait_job_completed(client, job_id: str, headers: dict, *, timeout_sec: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout_sec
    last = {}
    while time.monotonic() < deadline:
        r = client.get(f"{_p()}/ai-jobs/{job_id}", headers=headers)
        assert r.status_code == 200
        last = r.json()
        if last.get("status") == AiJobStatus.COMPLETED.value:
            return last
        time.sleep(0.02)
    assert False, f"job not completed: {last}"


def _wait_job_failed(client, job_id: str, headers: dict, *, timeout_sec: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout_sec
    last = {}
    while time.monotonic() < deadline:
        r = client.get(f"{_p()}/ai-jobs/{job_id}", headers=headers)
        assert r.status_code == 200
        last = r.json()
        if last.get("status") == AiJobStatus.FAILED.value:
            return last
        time.sleep(0.02)
    assert False, f"job not failed: {last}"


def test_author_create_job_mock_completes_and_list(client, db_session):
    """集成：创建为 ``pending``；后台 Mock 完成后 ``completed`` + ``output_payload`` 可读。"""
    vp = f"{_p()}/videos"
    _reg(client, "p15a1", "p15a1@example.com")
    ah = _login(client, "p15a1")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ah, json={"title": "ai target", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    r_create = client.post(
        f"{vp}/{vid}/ai-jobs",
        headers=ah,
        json={"job_type": "summary", "input_payload": {"lang": "zh"}},
    )
    assert r_create.status_code == 201
    job_id = r_create.json()["id"]
    assert r_create.json()["status"] == AiJobStatus.PENDING.value

    body = _wait_job_completed(client, job_id, ah)
    assert body["status"] == AiJobStatus.COMPLETED.value
    assert body.get("output_payload", {}).get("provider") == "mock"
    assert body["output_payload"].get("job_type") == "summary"

    r_list = client.get(f"{vp}/{vid}/ai-jobs", headers=ah, params={"limit": 20})
    assert r_list.status_code == 200
    assert int(r_list.headers.get("X-Total-Count", "0")) >= 1
    ids = [x["id"] for x in r_list.json()]
    assert job_id in ids


def test_worker_pending_processing_completed_chain_in_db(client, db_session):
    """同步校验状态机：``pending`` → ``processing``（running）→ ``completed``（success）+ mock 落库。"""
    from uuid import UUID

    from app.models.enums import AiJobType
    from app.repositories import ai_job_repository
    from app.services.ai_job_worker import (
        transition_pending_to_processing,
        transition_processing_to_completed_mock,
    )

    vp = f"{_p()}/videos"
    _reg(client, "p15chain", "p15chain@example.com")
    ah = _login(client, "p15chain")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ah, json={"title": "chain video", "tag_ids": []})
    vid = UUID(rv.json()["id"])
    _publish(client, vp, str(vid), ah, adm)

    job = ai_job_repository.create(
        db_session,
        video_id=vid,
        job_type=AiJobType.TRANSCRIPT,
        input_payload={"k": "v"},
    )
    db_session.commit()
    db_session.refresh(job)
    assert job.status == AiJobStatus.PENDING

    assert transition_pending_to_processing(db_session, job.id) is True
    db_session.refresh(job)
    assert job.status == AiJobStatus.PROCESSING

    assert transition_processing_to_completed_mock(db_session, job.id) is True
    db_session.refresh(job)
    assert job.status == AiJobStatus.COMPLETED
    assert job.output_payload is not None
    assert job.output_payload.get("provider") == "mock"
    assert job.output_payload.get("job_type") == "transcript"


def test_non_author_cannot_create_job_for_others_video(client, db_session):
    vp = f"{_p()}/videos"
    _reg(client, "p15own", "p15own@example.com")
    _reg(client, "p15peer", "p15peer@example.com")
    ho = _login(client, "p15own")
    hp = _login(client, "p15peer")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ho, json={"title": "mine only", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ho, adm)

    r403 = client.post(f"{vp}/{vid}/ai-jobs", headers=hp, json={"job_type": "transcript"})
    assert r403.status_code == 403
    assert r403.json().get("code") == AI_JOB_CREATE_FORBIDDEN


def test_admin_can_create_job_for_others_video(client, db_session):
    vp = f"{_p()}/videos"
    _reg(client, "p15u2", "p15u2@example.com")
    ah = _login(client, "p15u2")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ah, json={"title": "admin ai", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    r = client.post(f"{vp}/{vid}/ai-jobs", headers=adm, json={"job_type": "concept_extract"})
    assert r.status_code == 201
    jid = r.json()["id"]
    body = _wait_job_completed(client, jid, adm)
    assert body["status"] == AiJobStatus.COMPLETED.value


def test_peer_get_job_returns_404(client, db_session):
    vp = f"{_p()}/videos"
    _reg(client, "p15a3", "p15a3@example.com")
    _reg(client, "p15b3", "p15b3@example.com")
    ha = _login(client, "p15a3")
    hb = _login(client, "p15b3")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ha, json={"title": "secret job", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ha, adm)

    jid = client.post(f"{vp}/{vid}/ai-jobs", headers=ha, json={"job_type": "chapter_extract"}).json()["id"]

    r404 = client.get(f"{_p()}/ai-jobs/{jid}", headers=hb)
    assert r404.status_code == 404
    assert r404.json().get("code") == AI_JOB_NOT_FOUND


def test_mock_worker_exception_marks_job_failed(client, db_session, monkeypatch):
    """Mock 内部抛错时：``failed`` + ``error_message`` 写入库并可 GET。"""
    import app.services.ai_job_worker as job_worker

    def _boom(_db, _job_id):
        raise RuntimeError("simulated worker failure")

    monkeypatch.setattr(job_worker, "_run_mock_in_session", _boom)

    vp = f"{_p()}/videos"
    _reg(client, "p15fail", "p15fail@example.com")
    ah = _login(client, "p15fail")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ah, json={"title": "fail job video", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    r_create = client.post(f"{vp}/{vid}/ai-jobs", headers=ah, json={"job_type": "transcript"})
    assert r_create.status_code == 201
    job_id = r_create.json()["id"]

    body = _wait_job_failed(client, job_id, ah)
    assert body["status"] == AiJobStatus.FAILED.value
    assert body.get("output_payload") is None
    assert body.get("error_message")


def test_all_job_types_accepted(client, db_session):
    vp = f"{_p()}/videos"
    _reg(client, "p15a4", "p15a4@example.com")
    ah = _login(client, "p15a4")
    adm = _admin_hdr(db_session, client)

    rv = client.post(vp, headers=ah, json={"title": "types", "tag_ids": []})
    vid = rv.json()["id"]
    _publish(client, vp, vid, ah, adm)

    for jt in ("transcript", "summary", "concept_extract", "chapter_extract"):
        r = client.post(f"{vp}/{vid}/ai-jobs", headers=ah, json={"job_type": jt})
        assert r.status_code == 201, jt
        assert r.json()["job_type"] == jt
