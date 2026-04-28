"""阶段 11.3：GET /videos/{id}/play（GetVideoPlayAuth，Mock SDK）。"""

from __future__ import annotations

import uuid

from pydantic import SecretStr

from app.core.config import settings
from app.core.video_codes import (
    VIDEO_NOT_FOUND,
    VIDEO_PLAY_NO_MEDIA,
)
from app.core.vod_codes import VOD_CONFIG_INCOMPLETE
from app.infrastructure.aliyun_vod_api import VodPlayAuthResult


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


def _publish(client, p: str, vid: uuid.UUID, author_hdr: dict, admin_hdr: dict):
    assert client.post(f"{p}/{vid}/submit-review", headers=author_hdr).status_code == 200
    assert client.post(f"{p}/{vid}/approve", headers=admin_hdr).status_code == 200


def test_play_requires_login(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    r = client.get(f"{p}/{uuid.uuid4()}/play")
    assert r.status_code == 401


def test_play_published_logged_in_returns_play_auth(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.repositories import user_repository

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113a@example.com", "p113a")
    user_repository.create_user(
        db_session,
        email="p113adm2@example.com",
        username="p113adm2",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    ha = _login(client, "p113a")
    ahdr = _login(client, "p113adm2")
    vid = uuid.UUID(client.post(p, headers=ha, json={"title": "play", "tag_ids": []}).json()["id"])
    assert (
        client.patch(
            p + f"/{vid}/bind-vod",
            headers=ha,
            json={"vod_video_id": "vod-play-1"},
        ).status_code
        == 200
    )
    _publish(client, p, vid, ha, ahdr)

    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("sk"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
                "ALIYUN_VOD_PLAY_AUTH_TIMEOUT_SECONDS": 120,
            }
        ),
    )

    def _fake_play_auth(**_kwargs):
        return VodPlayAuthResult(play_auth="playauth-mock", request_id="req-mock")

    monkeypatch.setattr(vod_mod, "call_get_video_play_auth", _fake_play_auth)

    _register(client, "p113viewer@example.com", "p113viewer")
    hv = _login(client, "p113viewer")
    r = client.get(f"{p}/{vid}/play", headers=hv)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["video_id"] == str(vid)
    assert j.get("playback_mode") == "vod"
    assert j["vod_video_id"] == "vod-play-1"
    assert j["play_auth"] == "playauth-mock"
    assert j["request_id"] == "req-mock"
    assert j.get("expire_time") is not None
    assert "no-store" in (r.headers.get("cache-control") or "").lower()


def test_play_vod_not_bound_returns_400(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113b@example.com", "p113b")
    hb = _login(client, "p113b")
    vid = uuid.UUID(client.post(p, headers=hb, json={"title": "nobind", "tag_ids": []}).json()["id"])
    r = client.get(f"{p}/{vid}/play", headers=hb)
    assert r.status_code == 400
    assert r.json().get("code") == VIDEO_PLAY_NO_MEDIA


def test_play_offline_hidden_from_non_owner_returns_404(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.repositories import user_repository

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113c@example.com", "p113c")
    _register(client, "p113d@example.com", "p113d")
    user_repository.create_user(
        db_session,
        email="p113adm3@example.com",
        username="p113adm3",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    hc = _login(client, "p113c")
    hd = _login(client, "p113d")
    ahdr = _login(client, "p113adm3")
    vid = uuid.UUID(client.post(p, headers=hc, json={"title": "off", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=hc, json={"vod_video_id": "vod-off"})
    _publish(client, p, vid, hc, ahdr)
    assert client.patch(p + f"/{vid}", headers=hc, json={"status": "offline"}).status_code == 200

    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("sk"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
            }
        ),
    )
    monkeypatch.setattr(
        vod_mod,
        "call_get_video_play_auth",
        lambda **_k: VodPlayAuthResult(play_auth="x", request_id="r"),
    )

    r = client.get(f"{p}/{vid}/play", headers=hd)
    # 与详情一致：非作者/非管理员对 offline 资源不可见 → 404
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_play_offline_admin_can_play_others_video(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.repositories import user_repository

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113j@example.com", "p113j")
    user_repository.create_user(
        db_session,
        email="p113adm5@example.com",
        username="p113adm5",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    hj = _login(client, "p113j")
    ahdr = _login(client, "p113adm5")
    vid = uuid.UUID(client.post(p, headers=hj, json={"title": "admoff", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=hj, json={"vod_video_id": "vod-adm-off"})
    _publish(client, p, vid, hj, ahdr)
    assert client.post(f"{p}/{vid}/offline", headers=ahdr).status_code == 200

    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("sk"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
            }
        ),
    )
    monkeypatch.setattr(
        vod_mod,
        "call_get_video_play_auth",
        lambda **_k: VodPlayAuthResult(play_auth="admin-offline-play", request_id="r4"),
    )

    r = client.get(f"{p}/{vid}/play", headers=ahdr)
    assert r.status_code == 200
    assert r.json()["play_auth"] == "admin-offline-play"


def test_play_offline_author_still_ok(client, db_session, monkeypatch):
    from app.core.security import get_password_hash
    from app.models.enums import UserRole
    from app.repositories import user_repository

    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113e@example.com", "p113e")
    user_repository.create_user(
        db_session,
        email="p113adm4@example.com",
        username="p113adm4",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    he = _login(client, "p113e")
    ahdr = _login(client, "p113adm4")
    vid = uuid.UUID(client.post(p, headers=he, json={"title": "off2", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=he, json={"vod_video_id": "vod-off2"})
    _publish(client, p, vid, he, ahdr)
    assert client.patch(p + f"/{vid}", headers=he, json={"status": "offline"}).status_code == 200

    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("sk"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
            }
        ),
    )
    monkeypatch.setattr(
        vod_mod,
        "call_get_video_play_auth",
        lambda **_k: VodPlayAuthResult(play_auth="auth-offline-author", request_id="r2"),
    )

    r = client.get(f"{p}/{vid}/play", headers=he)
    assert r.status_code == 200
    assert r.json()["play_auth"] == "auth-offline-author"


def test_play_draft_other_user_404(client, db_session):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113f@example.com", "p113f")
    _register(client, "p113g@example.com", "p113g")
    hf = _login(client, "p113f")
    hg = _login(client, "p113g")
    vid = uuid.UUID(client.post(p, headers=hf, json={"title": "dr", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=hf, json={"vod_video_id": "vod-dr"})
    r = client.get(f"{p}/{vid}/play", headers=hg)
    assert r.status_code == 404
    assert r.json().get("code") == VIDEO_NOT_FOUND


def test_play_draft_author_ok(client, db_session, monkeypatch):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113h@example.com", "p113h")
    hh = _login(client, "p113h")
    vid = uuid.UUID(client.post(p, headers=hh, json={"title": "dr2", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=hh, json={"vod_video_id": "vod-dr2"})

    import app.services.vod_service as vod_mod

    monkeypatch.setattr(
        vod_mod,
        "settings",
        settings.model_copy(
            update={
                "ALIYUN_ACCESS_KEY_ID": "ak",
                "ALIYUN_ACCESS_KEY_SECRET": SecretStr("sk"),
                "ALIYUN_VOD_REGION": "cn-shanghai",
            }
        ),
    )
    monkeypatch.setattr(
        vod_mod,
        "call_get_video_play_auth",
        lambda **_k: VodPlayAuthResult(play_auth="draft-auth", request_id="r3"),
    )

    r = client.get(f"{p}/{vid}/play", headers=hh)
    assert r.status_code == 200
    assert r.json()["play_auth"] == "draft-auth"


def test_play_config_missing_503(client, db_session, monkeypatch):
    p = f"{settings.API_V1_PREFIX}/videos"
    _register(client, "p113i@example.com", "p113i")
    hi = _login(client, "p113i")
    vid = uuid.UUID(client.post(p, headers=hi, json={"title": "cfg", "tag_ids": []}).json()["id"])
    client.patch(p + f"/{vid}/bind-vod", headers=hi, json={"vod_video_id": "vod-cfg"})

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

    r = client.get(f"{p}/{vid}/play", headers=hi)
    assert r.status_code == 503
    assert r.json().get("code") == VOD_CONFIG_INCOMPLETE
