"""阶段 12：上传安全、upload_intents、日限流（内存 + Mock Redis HTTP，见 test_upload_rate_limit_phase12）。"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import app.services.vod_service as vod_service_module
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import get_password_hash
from app.core.upload_codes import (
    UPLOAD_COVER_EXTENSION_NOT_ALLOWED,
    UPLOAD_DAILY_QUOTA_EXCEEDED,
    UPLOAD_DESCRIPTION_TOO_LONG,
    UPLOAD_TITLE_TOO_LONG,
    UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED,
    UPLOAD_VIDEO_FILE_TOO_LARGE,
)
from app.core.vod_codes import VOD_API_ERROR
from app.models.upload_intent import UploadIntent
from app.infrastructure.aliyun_vod_api import VodCreateUploadResult
from app.models.enums import UserRole
from app.repositories import user_repository


def _prefix() -> str:
    return settings.API_V1_PREFIX


def _install_settings_everywhere(monkeypatch, new_settings):
    import app.core.config as cfg
    import app.core.upload_rate_limit as rl
    import app.core.upload_security as sec
    import app.services.vod_service as vod

    for mod in (cfg, sec, rl, vod):
        monkeypatch.setattr(mod, "settings", new_settings)


def _vod_ready_settings(**extra):
    return settings.model_copy(
        update={
            "ALIYUN_ACCESS_KEY_ID": "test-ak",
            "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
            "ALIYUN_VOD_REGION": "cn-shanghai",
            "VIDEO_UPLOAD_MAX_PER_USER_PER_DAY": 0,
            "VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS": False,
            **extra,
        },
    )


def _count_upload_intents(db_session) -> int:
    return int(db_session.execute(select(func.count()).select_from(UploadIntent)).scalar_one())


def _user_headers(client, *, username: str, email: str):
    assert (
        client.post(
            f"{_prefix()}/auth/register",
            json={"email": email, "username": username, "password": "secret1234"},
        ).status_code
        == 201
    )
    r2 = client.post(
        f"{_prefix()}/auth/login",
        data={"username": username, "password": "secret1234"},
    )
    assert r2.status_code == 200
    return {"Authorization": f"Bearer {r2.json()['access_token']}"}


def test_create_upload_rejects_disallowed_extension(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12a", email="up12a@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings())

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "clip.avi", "file_size": 100},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED


def test_create_upload_rejects_polyglot_last_extension_not_allowed(client, db_session, monkeypatch):
    """以「最后一段后缀」为准，``*.mp4.exe`` 等伪装扩展须被拒绝。"""
    hdr = _user_headers(client, username="up12poly", email="up12poly@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings())

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "clip.mp4.exe", "file_size": 100},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED


def test_create_upload_validation_error_does_not_write_upload_intent(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12intent0", email="up12intent0@example.com")
    before = _count_upload_intents(db_session)
    _install_settings_everywhere(monkeypatch, _vod_ready_settings())

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "bad.avi", "file_size": 10},
    )
    assert r.status_code == 400
    assert _count_upload_intents(db_session) == before


def test_create_upload_vod_failure_aborts_daily_slot_and_no_intent(client, db_session, monkeypatch):
    """占位后阿里云失败须 ``abort``，且不得写入 ``upload_intents``；下次同用户仍可成功。"""
    hdr = _user_headers(client, username="up12vodf", email="up12vodf@example.com")
    before = _count_upload_intents(db_session)
    _install_settings_everywhere(
        monkeypatch,
        _vod_ready_settings(VIDEO_UPLOAD_MAX_PER_USER_PER_DAY=2, VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS=False),
    )
    calls = {"n": 0}

    def _fake(**_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AppError("mock vod down", status_code=502, code=VOD_API_ERROR)
        return VodCreateUploadResult(
            video_id=f"vid-ok-{uuid.uuid4().hex[:8]}",
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    body = {"title": "t", "filename": "a.mp4", "file_size": 10}
    r1 = client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body)
    assert r1.status_code == 502
    assert _count_upload_intents(db_session) == before

    r2 = client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body)
    assert r2.status_code == 200
    assert _count_upload_intents(db_session) == before + 1


def test_create_upload_rejects_description_too_long(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12desc", email="up12desc@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings(MAX_VIDEO_DESCRIPTION_LENGTH=5))

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "a.mp4", "file_size": 10, "description": "123456"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_DESCRIPTION_TOO_LONG


def test_create_upload_accepts_uppercase_video_extension(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12uc", email="up12uc@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings())

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=f"vid-uc-{uuid.uuid4().hex[:8]}",
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "CLIP.MP4", "file_size": 10},
    )
    assert r.status_code == 200


def test_create_upload_rejects_oversized_file(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12b", email="up12b@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings(MAX_VIDEO_SIZE_MB=1))

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "clip.mp4", "file_size": 3 * 1024 * 1024},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_VIDEO_FILE_TOO_LARGE


def test_create_upload_rejects_bad_cover_extension(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12c", email="up12c@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings())

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={
            "title": "t",
            "filename": "clip.mp4",
            "file_size": 100,
            "cover_url": "https://cdn.example.com/x.bmp",
        },
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_COVER_EXTENSION_NOT_ALLOWED


def test_create_upload_rejects_title_over_limit(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12d", email="up12d@example.com")
    _install_settings_everywhere(monkeypatch, _vod_ready_settings(MAX_VIDEO_TITLE_LENGTH=3))

    def _fake(**_k):
        raise AssertionError("should not call VOD")

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "abcd", "filename": "c.mp4", "file_size": 1},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_TITLE_TOO_LONG


def test_create_upload_daily_limit_429(client, db_session, monkeypatch):
    hdr = _user_headers(client, username="up12e", email="up12e@example.com")
    _install_settings_everywhere(
        monkeypatch,
        _vod_ready_settings(VIDEO_UPLOAD_MAX_PER_USER_PER_DAY=2, VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS=False),
    )

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=f"vid-{uuid.uuid4().hex[:8]}",
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    body = {"title": "t", "filename": "a.mp4", "file_size": 10}
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200
    r3 = client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body)
    assert r3.status_code == 429
    assert r3.json().get("code") == UPLOAD_DAILY_QUOTA_EXCEEDED
    assert "Retry-After" in r3.headers


def test_create_upload_daily_limit_429_redis_path_mocked_http(client, db_session, monkeypatch):
    """HTTP 全链路：限流走 Redis 分支（Mock ``get_redis``），第三请求 429 且 ``INCR``/``EXPIRE``/``DECR`` 被调用。"""
    hdr = _user_headers(client, username="up12redis", email="up12redis@example.com")
    m = MagicMock()
    m.incr.side_effect = [1, 2, 3]
    monkeypatch.setattr("app.core.upload_rate_limit.get_redis", lambda: m)
    monkeypatch.setattr("app.core.upload_rate_limit.redis_available_cached", lambda: True)
    _install_settings_everywhere(
        monkeypatch,
        _vod_ready_settings(
            VIDEO_UPLOAD_MAX_PER_USER_PER_DAY=2,
            VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS=True,
            VIDEO_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY=True,
        ),
    )

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=f"vid-r-{uuid.uuid4().hex[:8]}",
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    body = {"title": "t", "filename": "a.mp4", "file_size": 10}
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200
    r3 = client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body)
    assert r3.status_code == 429
    assert r3.json().get("code") == UPLOAD_DAILY_QUOTA_EXCEEDED
    assert m.incr.call_count == 3
    m.expire.assert_called_once()
    m.decr.assert_called()


def test_admin_bypasses_daily_upload_limit(client, db_session, monkeypatch):
    user_repository.create_user(
        db_session,
        email="adm12@example.com",
        username="adm12",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    tok = client.post(
        f"{_prefix()}/auth/login",
        data={"username": "adm12", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}

    _install_settings_everywhere(
        monkeypatch,
        _vod_ready_settings(VIDEO_UPLOAD_MAX_PER_USER_PER_DAY=1, VIDEO_UPLOAD_RATE_LIMIT_USE_REDIS=False),
    )

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=f"vid-adm-{uuid.uuid4().hex[:6]}",
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_module, "call_create_upload_video", _fake)

    body = {"title": "t", "filename": "a.mp4", "file_size": 10}
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200
    assert client.post(f"{_prefix()}/uploads/vod/create-upload-video", headers=hdr, json=body).status_code == 200


def test_video_create_rejects_cover_with_bad_extension(client, db_session):
    user_repository.create_user(
        db_session,
        email="vc12@example.com",
        username="vc12",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{_prefix()}/auth/login",
        data={"username": "vc12", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        f"{_prefix()}/videos",
        headers=hdr,
        json={
            "title": "x",
            "tag_ids": [],
            "cover_url": "https://img.example/cover.gif",
        },
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_COVER_EXTENSION_NOT_ALLOWED


def test_bind_vod_rejects_bad_source_extension(client, db_session):
    user_repository.create_user(
        db_session,
        email="bd12@example.com",
        username="bd12",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    tok = client.post(
        f"{_prefix()}/auth/login",
        data={"username": "bd12", "password": "secret1234"},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    vid = client.post(f"{_prefix()}/videos", headers=hdr, json={"title": "b", "tag_ids": []}).json()["id"]
    r = client.patch(
        f"{_prefix()}/videos/{vid}/bind-vod",
        headers=hdr,
        json={"vod_video_id": "vod-x12", "source_file_name": "evil.avi"},
    )
    assert r.status_code == 400
    assert r.json().get("code") == UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED
