"""阶段 11.1：阿里云 VOD 上传凭证接口（Mock SDK，不触网）。"""

from __future__ import annotations

from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.models.upload_intent import UploadIntent
from app.infrastructure.aliyun_vod_api import VodCreateUploadResult


def _prefix() -> str:
    return settings.API_V1_PREFIX


def _register_login(client, *, username: str = "vod111u", email: str = "vod111u@example.com"):
    r = client.post(
        f"{_prefix()}/auth/register",
        json={"email": email, "username": username, "password": "secret1234"},
    )
    assert r.status_code == 201, r.text
    r2 = client.post(
        f"{_prefix()}/auth/login",
        data={"username": username, "password": "secret1234"},
    )
    assert r2.status_code == 200, r2.text
    return {"Authorization": f"Bearer {r2.json()['access_token']}"}


def test_vod_create_upload_requires_auth(client):
    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        json={"title": "t", "filename": "a.mp4", "file_size": 1},
    )
    assert r.status_code == 401


def test_vod_create_upload_validation_filename_no_ext(client):
    hdr = _register_login(client, username="vod111b", email="vod111b@example.com")
    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "t", "filename": "badnoext", "file_size": 1},
    )
    assert r.status_code == 422


def test_vod_create_upload_config_missing_returns_503(client, monkeypatch):
    hdr = _register_login(client, username="vod111c", email="vod111c@example.com")
    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": None,
                "ALIYUN_ACCESS_KEY_SECRET": None,
                "ALIYUN_VOD_REGION": None,
            }
        ),
    )
    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={"title": "我的视频", "filename": "clip.mp4", "file_size": 1024},
    )
    assert r.status_code == 503
    assert r.json().get("code") == "VOD_CONFIG_INCOMPLETE"


def test_vod_create_upload_success_with_mock_sdk(client, db_session, monkeypatch):
    hdr = _register_login(client, username="vod111d", email="vod111d@example.com")
    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "test-ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("test-secret-123456789012"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
            }
        ),
    )

    def _fake_call(**_kwargs):
        return VodCreateUploadResult(
            video_id="vid-mock-1",
            upload_address="addr-b64-mock",
            upload_auth="auth-b64-mock",
            request_id="req-mock-1",
        )

    monkeypatch.setattr(vod_mod, "call_create_upload_video", _fake_call)

    r = client.post(
        f"{_prefix()}/uploads/vod/create-upload-video",
        headers=hdr,
        json={
            "title": "  标题  ",
            "filename": "movie.mp4",
            "file_size": 2048,
            "description": "  简介  ",
            "cover_url": "https://cdn.example.com/cover.jpg",
        },
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["video_id_from_vod"] == "vid-mock-1"
    assert j["upload_address"] == "addr-b64-mock"
    assert j["upload_auth"] == "auth-b64-mock"
    assert j["request_id"] == "req-mock-1"
    body = str(j).lower()
    assert "access_key" not in body
    assert "secret" not in body

    intents = db_session.execute(select(UploadIntent).where(UploadIntent.vod_video_id == "vid-mock-1")).scalars().all()
    assert len(intents) == 1
    assert intents[0].filename == "movie.mp4"
    assert intents[0].file_size == 2048
    assert intents[0].status == "issued"
