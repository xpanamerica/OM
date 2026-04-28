"""VOD RefreshUploadVideo：权限与阿里云薄封装（单测 mock）。"""

from __future__ import annotations

import app.services.vod_service as vod_service_mod
from app.core.config import settings
from app.core.security import get_password_hash
from app.core import config as app_config
from app.core.vod_codes import VOD_REFRESH_UPLOAD_FORBIDDEN, VOD_REFRESH_UPLOAD_RATE_LIMITED
from app.infrastructure.aliyun_vod_api import VodCreateUploadResult
from app.models.enums import UserRole
from app.models.upload_intent import UploadIntent
from app.repositories import user_repository
from pydantic import SecretStr


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_refresh_upload_forbidden_without_intent(client, db_session, monkeypatch):
    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={"email": "refvod1@example.com", "username": "refvod1", "password": "secret1234"},
        ).status_code
        == 201
    )
    hdr = _login(client, "refvod1")

    def _no_sdk(**_k):
        raise AssertionError("must not call VOD without intent")

    monkeypatch.setattr(vod_service_mod, "call_refresh_upload_video", _no_sdk)

    r = client.post(
        f"{settings.API_V1_PREFIX}/uploads/vod/refresh-upload-video",
        headers=hdr,
        json={"vod_video_id": "vod-no-intent-xyz"},
    )
    assert r.status_code == 403
    assert r.json().get("code") == VOD_REFRESH_UPLOAD_FORBIDDEN


def test_refresh_upload_ok_with_intent(client, db_session, monkeypatch):
    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={"email": "refvod2@example.com", "username": "refvod2", "password": "secret1234"},
        ).status_code
        == 201
    )
    hdr = _login(client, "refvod2")
    u = user_repository.get_by_username(db_session, "refvod2")
    assert u is not None
    vid = "vod-intent-refresh-1"
    db_session.add(
        UploadIntent(
            user_id=u.id,
            filename="clip.mp4",
            file_size=123,
            vod_video_id=vid,
        )
    )
    db_session.commit()

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=vid,
            upload_address="addr2",
            upload_auth="auth2",
            request_id="rid2",
        )

    monkeypatch.setattr(vod_service_mod, "call_refresh_upload_video", _fake)
    _vod_ready = settings.model_copy(
        update={
            "ALIYUN_ACCESS_KEY_ID": "test-ak",
            "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
            "ALIYUN_VOD_REGION": "cn-shanghai",
        },
    )
    monkeypatch.setattr(vod_service_mod, "settings", _vod_ready)

    r = client.post(
        f"{settings.API_V1_PREFIX}/uploads/vod/refresh-upload-video",
        headers=hdr,
        json={"vod_video_id": vid},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["video_id_from_vod"] == vid
    assert j["upload_address"] == "addr2"
    assert j["upload_auth"] == "auth2"


def test_refresh_upload_admin_bypass_intent(client, db_session, monkeypatch):
    user_repository.create_user(
        db_session,
        email="refvodadm@example.com",
        username="refvodadm",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    hdr = _login(client, "refvodadm")

    vod_id = "vod-admin-refresh-only"

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=vod_id,
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_mod, "call_refresh_upload_video", _fake)
    _vod_ready = settings.model_copy(
        update={
            "ALIYUN_ACCESS_KEY_ID": "test-ak",
            "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
            "ALIYUN_VOD_REGION": "cn-shanghai",
        },
    )
    monkeypatch.setattr(vod_service_mod, "settings", _vod_ready)

    r = client.post(
        f"{settings.API_V1_PREFIX}/uploads/vod/refresh-upload-video",
        headers=hdr,
        json={"vod_video_id": vod_id},
    )
    assert r.status_code == 200, r.text


def test_refresh_upload_rate_limited(client, db_session, monkeypatch):
    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={"email": "refvodrl@example.com", "username": "refvodrl", "password": "secret1234"},
        ).status_code
        == 201
    )
    hdr = _login(client, "refvodrl")
    u = user_repository.get_by_username(db_session, "refvodrl")
    assert u is not None
    vid = "vod-intent-refresh-rl"
    db_session.add(
        UploadIntent(
            user_id=u.id,
            filename="clip.mp4",
            file_size=123,
            vod_video_id=vid,
        )
    )
    db_session.commit()

    def _fake(**_k):
        return VodCreateUploadResult(
            video_id=vid,
            upload_address="addr",
            upload_auth="auth",
            request_id="rid",
        )

    monkeypatch.setattr(vod_service_mod, "call_refresh_upload_video", _fake)
    _vod_ready = settings.model_copy(
        update={
            "ALIYUN_ACCESS_KEY_ID": "test-ak",
            "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
            "ALIYUN_VOD_REGION": "cn-shanghai",
        },
    )
    monkeypatch.setattr(vod_service_mod, "settings", _vod_ready)
    monkeypatch.setattr(app_config.settings, "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE", 2, raising=False)

    url = f"{settings.API_V1_PREFIX}/uploads/vod/refresh-upload-video"
    assert client.post(url, headers=hdr, json={"vod_video_id": vid}).status_code == 200
    assert client.post(url, headers=hdr, json={"vod_video_id": vid}).status_code == 200
    r3 = client.post(url, headers=hdr, json={"vod_video_id": vid})
    assert r3.status_code == 429
    assert r3.json().get("code") == VOD_REFRESH_UPLOAD_RATE_LIMITED


def test_refresh_upload_admin_not_rate_limited(client, db_session, monkeypatch):
    user_repository.create_user(
        db_session,
        email="refvodadrl@example.com",
        username="refvodadrl",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    hdr = _login(client, "refvodadrl")
    vod_id = "vod-admin-rl-bypass"

    n_calls = {"n": 0}

    def _fake(**_k):
        n_calls["n"] += 1
        return VodCreateUploadResult(
            video_id=vod_id,
            upload_address="a",
            upload_auth="b",
            request_id="r",
        )

    monkeypatch.setattr(vod_service_mod, "call_refresh_upload_video", _fake)
    _vod_ready = settings.model_copy(
        update={
            "ALIYUN_ACCESS_KEY_ID": "test-ak",
            "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
            "ALIYUN_VOD_REGION": "cn-shanghai",
        },
    )
    monkeypatch.setattr(vod_service_mod, "settings", _vod_ready)
    monkeypatch.setattr(app_config.settings, "VOD_REFRESH_UPLOAD_MAX_PER_USER_PER_MINUTE", 1, raising=False)

    url = f"{settings.API_V1_PREFIX}/uploads/vod/refresh-upload-video"
    assert client.post(url, headers=hdr, json={"vod_video_id": vod_id}).status_code == 200
    assert client.post(url, headers=hdr, json={"vod_video_id": vod_id}).status_code == 200
    assert n_calls["n"] == 2
