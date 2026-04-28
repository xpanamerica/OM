"""阶段 11.4：POST /uploads/vod/callback（VOD 事件 → 本地状态同步）。"""

from __future__ import annotations

import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core import config
from app.core.config import settings
from app.core.vod_codes import (
    VOD_CALLBACK_INVALID_JSON,
    VOD_CALLBACK_NOT_CONFIGURED,
    VOD_CALLBACK_UNAUTHORIZED,
    VOD_CALLBACK_VIDEO_ID_MISSING,
    VOD_CALLBACK_VIDEO_NOT_FOUND,
)
from app.models.enums import UserRole, VideoStatus, VodTranscodeStatus, VodUploadStatus
from app.models.video import Video


def _cb_url() -> str:
    return f"{settings.API_V1_PREFIX}/uploads/vod/callback"


def _secret_headers(secret: str) -> dict[str, str]:
    return {"X-VOD-Callback-Secret": secret}


def test_callback_requires_configured_secret(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": None}),
    )
    r = client.post(
        _cb_url(),
        headers=_secret_headers("x"),
        json={"EventType": "FileUploadComplete"},
    )
    assert r.status_code == 503
    assert r.json().get("code") == VOD_CALLBACK_NOT_CONFIGURED


def test_callback_rejects_bad_secret(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("expected-cb-secret")}),
    )
    r = client.post(
        _cb_url(),
        headers=_secret_headers("wrong"),
        json={"EventType": "FileUploadComplete", "VideoId": "v1", "Status": "success"},
    )
    assert r.status_code == 401
    assert r.json().get("code") == VOD_CALLBACK_UNAUTHORIZED


def test_callback_rejects_missing_or_blank_secret_header(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("expected-cb-secret")}),
    )
    r_no_hdr = client.post(
        _cb_url(),
        json={"EventType": "FileUploadComplete", "VideoId": "v1", "Status": "success"},
    )
    assert r_no_hdr.status_code == 401
    assert r_no_hdr.json().get("code") == VOD_CALLBACK_UNAUTHORIZED

    r_blank = client.post(
        _cb_url(),
        headers={"X-VOD-Callback-Secret": "  \t  "},
        json={"EventType": "FileUploadComplete", "VideoId": "v1", "Status": "success"},
    )
    assert r_blank.status_code == 401
    assert r_blank.json().get("code") == VOD_CALLBACK_UNAUTHORIZED


def test_callback_invalid_json(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("s")}),
    )
    r = client.post(
        _cb_url(),
        headers=_secret_headers("s"),
        content=b"not json",
    )
    assert r.status_code == 400
    assert r.json().get("code") == VOD_CALLBACK_INVALID_JSON


def test_callback_upload_complete_updates_video(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114")}),
    )

    p = f"{settings.API_V1_PREFIX}/videos"
    user_repository.create_user(
        db_session,
        email="cb114@example.com",
        username="cb114",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    r_login = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "cb114", "password": "secret1234"},
    )
    hdr = {"Authorization": f"Bearer {r_login.json()['access_token']}"}
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "cb", "tag_ids": []}).json()["id"])
    vod_id = "vod-cb-114"
    assert (
        client.patch(
            p + f"/{vid}/bind-vod",
            headers=hdr,
            json={"vod_video_id": vod_id},
        ).status_code
        == 200
    )

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114"),
        json={
            "EventType": "FileUploadComplete",
            "VideoId": vod_id,
            "Status": "success",
            "EventTime": "2017-03-20T07:49:17Z",
        },
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is True
    assert j["updated"] is True
    assert j["event_kind"] == "upload_complete"
    assert j["video_id"] == str(vid)

    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.upload_status == VodUploadStatus.UPLOADED
    assert row.transcode_status == VodTranscodeStatus.PENDING
    assert row.status == VideoStatus.DRAFT


def test_callback_transcode_complete_unknown_vod_returns_404(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114b")}),
    )

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114b"),
        json={
            "EventType": "TranscodeComplete",
            "VideoId": "no-such-vod-in-db",
            "Status": "success",
            "StreamInfos": [{"Status": "success", "Duration": 42}],
        },
    )
    assert r.status_code == 404
    assert r.json().get("code") == VOD_CALLBACK_VIDEO_NOT_FOUND


def test_callback_transcode_complete_missing_video_id_returns_400(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114b2")}),
    )
    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114b2"),
        json={"EventType": "TranscodeComplete", "Status": "success"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == VOD_CALLBACK_VIDEO_ID_MISSING


def test_callback_transcode_complete_sets_duration(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114c")}),
    )
    user_repository.create_user(
        db_session,
        email="cb114c@example.com",
        username="cb114c",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "cb114c", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "tc", "tag_ids": []}).json()["id"])
    vod_id = "vod-tc-114"
    client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": vod_id})

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114c"),
        json={
            "EventType": "TranscodeComplete",
            "VideoId": vod_id,
            "Status": "success",
            "StreamInfos": [
                {"Status": "success", "Duration": 10},
                {"Status": "success", "Duration": 99},
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "transcode_complete"
    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.transcode_status == VodTranscodeStatus.COMPLETED
    assert row.duration_seconds == 99
    assert row.status == VideoStatus.DRAFT


def test_callback_transcode_failed(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114d")}),
    )
    user_repository.create_user(
        db_session,
        email="cb114d@example.com",
        username="cb114d",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "cb114d", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "tf", "tag_ids": []}).json()["id"])
    vod_id = "vod-tf-114"
    client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": vod_id})

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114d"),
        json={"EventType": "TranscodeComplete", "VideoId": vod_id, "Status": "fail"},
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "transcode_failed"
    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.transcode_status == VodTranscodeStatus.FAILED
    assert row.status == VideoStatus.DRAFT


@pytest.mark.parametrize(
    ("event_type", "email", "username", "vod_suffix"),
    [
        ("StreamTranscodeComplete", "cb114st@example.com", "cb114st", "st"),
        ("AllTranscodeComplete", "cb114at@example.com", "cb114at", "at"),
    ],
)
def test_callback_transcode_complete_event_type_aliases(
    client, db_session, monkeypatch, event_type, email, username, vod_suffix
):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114-alias")}),
    )
    user_repository.create_user(
        db_session,
        email=email,
        username=username,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "alias", "tag_ids": []}).json()["id"])
    vod_id = f"vod-alias-{vod_suffix}"
    client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": vod_id})

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114-alias"),
        json={
            "EventType": event_type,
            "VideoId": vod_id,
            "Status": "success",
            "StreamInfos": [{"Status": "success", "Duration": 55}],
        },
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "transcode_complete"
    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.transcode_status == VodTranscodeStatus.COMPLETED
    assert row.duration_seconds == 55
    assert row.status == VideoStatus.DRAFT


@pytest.mark.parametrize(
    ("event_type", "email", "username", "vod_suffix"),
    [
        ("TranscodeFail", "cb114tf2@example.com", "cb114tf2", "tf2"),
        ("TranscodeFailed", "cb114tfd@example.com", "cb114tfd", "tfd"),
    ],
)
def test_callback_transcode_failed_event_type_aliases(
    client, db_session, monkeypatch, event_type, email, username, vod_suffix
):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114-fail-alias")}),
    )
    user_repository.create_user(
        db_session,
        email=email,
        username=username,
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "fail-alias", "tag_ids": []}).json()["id"])
    vod_id = f"vod-fail-alias-{vod_suffix}"
    client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": vod_id})

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114-fail-alias"),
        json={"EventType": event_type, "VideoId": vod_id},
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "transcode_failed"
    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.transcode_status == VodTranscodeStatus.FAILED
    assert row.status == VideoStatus.DRAFT


def test_callback_upload_complete_fail_sets_upload_failed(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.repositories import user_repository

    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114-up-fail")}),
    )
    user_repository.create_user(
        db_session,
        email="cb114upf@example.com",
        username="cb114upf",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "cb114upf", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    p = f"{settings.API_V1_PREFIX}/videos"
    vid = uuid.UUID(client.post(p, headers=hdr, json={"title": "up-fail", "tag_ids": []}).json()["id"])
    vod_id = "vod-up-fail-114"
    client.patch(p + f"/{vid}/bind-vod", headers=hdr, json={"vod_video_id": vod_id})

    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114-up-fail"),
        json={"EventType": "FileUploadComplete", "VideoId": vod_id, "Status": "fail"},
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "upload_complete"
    row = db_session.execute(select(Video).where(Video.id == vid)).scalar_one()
    assert row.upload_status == VodUploadStatus.FAILED
    assert row.status == VideoStatus.DRAFT


def test_callback_unknown_event_noop(client, db_session, monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        settings.model_copy(update={"ALIYUN_VOD_CALLBACK_SECRET": SecretStr("cb-114e")}),
    )
    r = client.post(
        _cb_url(),
        headers=_secret_headers("cb-114e"),
        json={"EventType": "SnapshotComplete", "VideoId": "x"},
    )
    assert r.status_code == 200
    assert r.json()["event_kind"] == "unknown"
    assert r.json()["updated"] is False
