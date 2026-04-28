"""本机成片上传与 GET …/play /local-stream 链路。"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


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


def test_local_upload_then_play_returns_stream_url(client, db_session, tmp_path, monkeypatch):
    import app.services.local_video_media_service as loc_mod

    monkeypatch.setattr(loc_mod, "settings", settings.model_copy(update={"LOCAL_VIDEO_STORAGE_DIR": str(tmp_path)}))

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "locv1@example.com", "locv1")
    ha = _login(client, "locv1")
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "local clip", "tag_ids": []}).json()["id"])

    mp4ish = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    up = client.post(
        f"{p}/{vid}/local-media",
        headers=ha,
        files={"file": ("clip.mp4", io.BytesIO(mp4ish), "video/mp4")},
    )
    assert up.status_code == 200, up.text

    r = client.get(f"{p}/{vid}/play", headers=ha)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["playback_mode"] == "local"
    assert j["stream_url"]
    assert "local-stream" in j["stream_url"]
    assert j.get("play_auth") in (None, "")
    assert j.get("vod_video_id") in (None, "")

    pu = urlparse(j["stream_url"])
    r2 = client.get(pu.path + "?" + pu.query)
    assert r2.status_code == 200, r2.text
    assert len(r2.content) == len(mp4ish)

    stored = Path(tmp_path) / f"{vid}.mp4"
    assert stored.is_file()


def test_local_upload_binary_put_then_play(client, db_session, tmp_path, monkeypatch):
    import app.services.local_video_media_service as loc_mod

    monkeypatch.setattr(loc_mod, "settings", settings.model_copy(update={"LOCAL_VIDEO_STORAGE_DIR": str(tmp_path)}))

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "locbin@example.com", "locbin")
    ha = _login(client, "locbin")
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "binary clip", "tag_ids": []}).json()["id"])

    mp4ish = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    up = client.put(
        f"{p}/{vid}/local-media-binary?suffix=.mp4&source_name=clip.mp4",
        headers={**ha, "Content-Type": "application/octet-stream"},
        content=mp4ish,
    )
    assert up.status_code == 200, up.text
    assert (Path(tmp_path) / f"{vid}.mp4").is_file()

    r = client.get(f"{p}/{vid}/play", headers=ha)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["playback_mode"] == "local"
    assert "local-stream" in j["stream_url"]

    pu = urlparse(j["stream_url"])
    r2 = client.get(pu.path + "?" + pu.query)
    assert r2.status_code == 200
    assert len(r2.content) == len(mp4ish)
