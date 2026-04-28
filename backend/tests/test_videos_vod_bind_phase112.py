"""阶段 11.2：videos 表绑定阿里云 VOD VideoId。"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.video_codes import (
    VIDEO_IDEMPOTENCY_CONFLICT,
    VIDEO_NOT_FOUND,
    VIDEO_BIND_VOD_FORBIDDEN,
    VIDEO_VOD_ALREADY_BOUND,
    VIDEO_VOD_FIELDS_PATCH_FORBIDDEN,
    VIDEO_VOD_ID_CONFLICT,
    VIDEO_VOD_ID_CREATE_FORBIDDEN,
)
from app.models.enums import UserRole, VodTranscodeStatus, VodUploadStatus
from app.repositories import user_repository


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
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


def _admin_headers(db_session, client):
    user_repository.create_user(
        db_session,
        email="vod112adm@example.com",
        username="vod112adm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return _login(client, "vod112adm")


def test_create_with_vod_id_forbidden_for_user(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u1@example.com", "vod112u1")
    hdr = _login(client, "vod112u1")
    r = client.post(
        p,
        headers=hdr,
        json={"title": "t", "tag_ids": [], "vod_video_id": "vod-abc-1"},
    )
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_VOD_ID_CREATE_FORBIDDEN


def test_create_with_vod_id_ok_for_admin(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    ahdr = _admin_headers(db_session, client)
    r = client.post(
        p,
        headers=ahdr,
        json={"title": "adm vod", "tag_ids": [], "vod_video_id": "vod-admin-create-1"},
    )
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["vod_video_id"] == "vod-admin-create-1"
    assert j["upload_status"] == VodUploadStatus.PENDING.value
    assert j["transcode_status"] == VodTranscodeStatus.PENDING.value


def test_create_vod_id_conflict_second_admin_video(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    ahdr = _admin_headers(db_session, client)
    vid = "vod-dup-1"
    r1 = client.post(p, headers=ahdr, json={"title": "a1", "tag_ids": [], "vod_video_id": vid})
    assert r1.status_code == 201
    r2 = client.post(p, headers=ahdr, json={"title": "a2", "tag_ids": [], "vod_video_id": vid})
    assert r2.status_code == 409
    assert r2.json().get("code") == VIDEO_VOD_ID_CONFLICT


def test_bind_vod_author_first_bind(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u2@example.com", "vod112u2")
    hdr = _login(client, "vod112u2")
    r0 = client.post(p, headers=hdr, json={"title": "mine", "tag_ids": []})
    assert r0.status_code == 201
    vid = uuid.UUID(r0.json()["id"])
    assert r0.json()["vod_video_id"] is None
    assert r0.json()["upload_status"] == VodUploadStatus.NOT_STARTED.value

    r = client.patch(
        p + f"/{vid}/bind-vod",
        headers=hdr,
        json={"vod_video_id": "vod-bind-author-1", "duration_seconds": 120, "source_file_name": "a.mp4"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["vod_video_id"] == "vod-bind-author-1"
    assert j["upload_status"] == VodUploadStatus.PENDING.value
    assert j["transcode_status"] == VodTranscodeStatus.PENDING.value
    assert j["duration_seconds"] == 120
    assert j["source_file_name"] == "a.mp4"


def test_bind_vod_forbidden_non_author(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u3@example.com", "vod112u3")
    _register(client, "vod112u4@example.com", "vod112u4")
    h3 = _login(client, "vod112u3")
    h4 = _login(client, "vod112u4")
    r0 = client.post(p, headers=h3, json={"title": "v3", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    r = client.patch(
        p + f"/{vid}/bind-vod",
        headers=h4,
        json={"vod_video_id": "vod-x"},
    )
    # 他人草稿与 GET 详情一致：404，不暴露资源存在
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_bind_vod_forbidden_non_author_published_is_403(client, db_session):
    """已发布视频对登录用户可见；非作者绑定返回 403。"""
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112puba@example.com", "vod112puba")
    _register(client, "vod112pubb@example.com", "vod112pubb")
    ha = _login(client, "vod112puba")
    hb = _login(client, "vod112pubb")
    ahdr = _admin_headers(db_session, client)
    r0 = client.post(p, headers=ha, json={"title": "pub", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    assert client.post(f"{p}/{vid}/submit-review", headers=ha).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200
    r = client.patch(p + f"/{vid}/bind-vod", headers=hb, json={"vod_video_id": "vod-pub-x"})
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_BIND_VOD_FORBIDDEN


def test_bind_vod_already_bound_user(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u5@example.com", "vod112u5")
    hdr = _login(client, "vod112u5")
    r0 = client.post(p, headers=hdr, json={"title": "v5", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    r1 = client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": "vod-once"})
    assert r1.status_code == 200
    r2 = client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": "vod-twice"})
    assert r2.status_code == 409
    assert r2.json().get("code") == VIDEO_VOD_ALREADY_BOUND


def test_bind_vod_admin_can_rebind(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u6@example.com", "vod112u6")
    hdr = _login(client, "vod112u6")
    ahdr = _admin_headers(db_session, client)
    r0 = client.post(p, headers=hdr, json={"title": "v6", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    r1 = client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": "vod-a"})
    assert r1.status_code == 200
    r2 = client.patch(p + f"/{vid}/bind-vod", headers=ahdr, json={"vod_video_id": "vod-b"})
    assert r2.status_code == 200
    assert r2.json()["vod_video_id"] == "vod-b"


def test_bind_vod_id_in_use_elsewhere(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u7@example.com", "vod112u7")
    _register(client, "vod112u8@example.com", "vod112u8")
    h7 = _login(client, "vod112u7")
    h8 = _login(client, "vod112u8")
    r7 = client.post(p, headers=h7, json={"title": "v7", "tag_ids": []})
    r8 = client.post(p, headers=h8, json={"title": "v8", "tag_ids": []})
    vid7 = uuid.UUID(r7.json()["id"])
    vid8 = uuid.UUID(r8.json()["id"])
    shared = "vod-shared-lock"
    assert client.patch(p + f"/{vid7}/bind-vod", headers=h7, json={"vod_video_id": shared}).status_code == 200
    r = client.patch(p + f"/{vid8}/bind-vod", headers=h8, json={"vod_video_id": shared})
    assert r.status_code == 409
    assert r.json().get("code") == VIDEO_VOD_ID_CONFLICT


def test_user_cannot_patch_vod_status_fields(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u9@example.com", "vod112u9")
    hdr = _login(client, "vod112u9")
    r0 = client.post(p, headers=hdr, json={"title": "v9", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    r = client.patch(
        p + f"/{vid}",
        headers=hdr,
        json={"upload_status": VodUploadStatus.UPLOADED.value},
    )
    assert r.status_code == 403
    assert r.json().get("code") == VIDEO_VOD_FIELDS_PATCH_FORBIDDEN


def test_bind_vod_idempotency_replay(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112idem@example.com", "vod112idem")
    hdr = _login(client, "vod112idem")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "idem", "tag_ids": []}).json()["id"])
    idem = {"Idempotency-Key": "bind-idem-1"}
    body = {"vod_video_id": "vod-idem-replay"}
    r1 = client.patch(p + f"/{vid}/bind-vod", headers={**hdr, **idem}, json=body)
    assert r1.status_code == 200, r1.text
    r2 = client.patch(p + f"/{vid}/bind-vod", headers={**hdr, **idem}, json=body)
    assert r2.status_code == 200
    assert r2.json()["vod_video_id"] == r1.json()["vod_video_id"]


def test_bind_vod_idempotency_conflict(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112idem2@example.com", "vod112idem2")
    hdr = _login(client, "vod112idem2")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "idem2", "tag_ids": []}).json()["id"])
    idem = {"Idempotency-Key": "bind-idem-2"}
    assert (
        client.patch(
            p + f"/{vid}/bind-vod",
            headers={**hdr, **idem},
            json={"vod_video_id": "vod-a"},
        ).status_code
        == 200
    )
    r2 = client.patch(
        p + f"/{vid}/bind-vod",
        headers={**hdr, **idem},
        json={"vod_video_id": "vod-b"},
    )
    assert r2.status_code == 409
    assert r2.json().get("code") == VIDEO_IDEMPOTENCY_CONFLICT


def test_bind_vod_rejects_pathlike_source_file_name(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112path@example.com", "vod112path")
    hdr = _login(client, "vod112path")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "p", "tag_ids": []}).json()["id"])
    r = client.patch(
        p + f"/{vid}/bind-vod",
        headers=hdr,
        json={"vod_video_id": "vod-ok", "source_file_name": "../../etc/passwd"},
    )
    assert r.status_code == 422


def test_bind_vod_rejects_oversized_duration(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112dur@example.com", "vod112dur")
    hdr = _login(client, "vod112dur")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "d", "tag_ids": []}).json()["id"])
    r = client.patch(
        p + f"/{vid}/bind-vod",
        headers=hdr,
        json={"vod_video_id": "vod-dur", "duration_seconds": 604_801},
    )
    assert r.status_code == 422


def test_bind_vod_rejects_whitespace_in_vod_video_id(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112sp@example.com", "vod112sp")
    hdr = _login(client, "vod112sp")
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "s", "tag_ids": []}).json()["id"])
    r = client.patch(
        p + f"/{vid}/bind-vod",
        headers=hdr,
        json={"vod_video_id": "bad id"},
    )
    assert r.status_code == 422


def test_published_vod_binding_redacted_for_anon_and_peer(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112priva@example.com", "vod112priva")
    _register(client, "vod112privb@example.com", "vod112privb")
    ha = _login(client, "vod112priva")
    hb = _login(client, "vod112privb")
    ahdr = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "pv", "tag_ids": []}).json()["id"])
    assert (
        client.patch(p + f"/{vid}/bind-vod", headers=ha, json={"vod_video_id": "vod-secret-x"}).status_code
        == 200
    )
    assert client.post(f"{p}/{vid}/submit-review", headers=ha).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200

    r_anon = client.get(f"{p}/{vid}")
    assert r_anon.status_code == 200
    assert r_anon.json()["vod_video_id"] is None
    assert r_anon.json()["source_file_name"] is None

    r_peer = client.get(f"{p}/{vid}", headers=hb)
    assert r_peer.status_code == 200
    assert r_peer.json()["vod_video_id"] is None

    r_author = client.get(f"{p}/{vid}", headers=ha)
    assert r_author.json()["vod_video_id"] == "vod-secret-x"

    r_list_anon = client.get(p)
    assert len(r_list_anon.json()) == 1
    assert r_list_anon.json()[0]["vod_video_id"] is None
    r_list_author = client.get(p, headers=ha)
    assert r_list_author.json()[0]["vod_video_id"] == "vod-secret-x"


def test_admin_sees_others_vod_binding_in_get(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112own@example.com", "vod112own")
    ho = _login(client, "vod112own")
    ahdr = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(p, headers=ho, json={"title": "own", "tag_ids": []}).json()["id"])
    assert (
        client.patch(p + f"/{vid}/bind-vod", headers=ho, json={"vod_video_id": "vod-admin-see"}).status_code
        == 200
    )
    r = client.get(f"{p}/{vid}", headers=ahdr)
    assert r.status_code == 200
    assert r.json()["vod_video_id"] == "vod-admin-see"


def test_video_detail_etag_differs_redacted_vs_full(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112etag@example.com", "vod112etag")
    h = _login(client, "vod112etag")
    ahdr = _admin_headers(db_session, client)
    vid = uuid.UUID(client.post(p, headers=h, json={"title": "e", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=h, json={"vod_video_id": "vod-etag-tier"})
    assert client.post(f"{p}/{vid}/submit-review", headers=h).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=ahdr).status_code == 200
    e_anon = client.get(f"{p}/{vid}").headers.get("etag")
    e_author = client.get(f"{p}/{vid}", headers=h).headers.get("etag")
    assert e_anon and e_author
    assert e_anon != e_author


def test_admin_can_patch_vod_status_fields(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "vod112u10@example.com", "vod112u10")
    hdr = _login(client, "vod112u10")
    ahdr = _admin_headers(db_session, client)
    r0 = client.post(p, headers=hdr, json={"title": "v10", "tag_ids": []})
    vid = uuid.UUID(r0.json()["id"])
    r = client.patch(
        p + f"/{vid}",
        headers=ahdr,
        json={
            "upload_status": VodUploadStatus.UPLOADED.value,
            "transcode_status": VodTranscodeStatus.COMPLETED.value,
        },
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["upload_status"] == VodUploadStatus.UPLOADED.value
    assert j["transcode_status"] == VodTranscodeStatus.COMPLETED.value
