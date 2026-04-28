"""稿件附件：作者上传、列表、下载。"""

from __future__ import annotations

import io

import app.core.config as app_config
from app.core.config import settings
from app.core.upload_codes import (
    UPLOAD_ATTACHMENT_EXTENSION_NOT_ALLOWED,
    UPLOAD_ATTACHMENT_MAGIC_MISMATCH,
    UPLOAD_ATTACHMENT_RATE_LIMITED,
)


def _register_and_login(client, email: str, username: str):
    assert (
        client.post(
            f"{settings.API_V1_PREFIX}/auth/register",
            json={"email": email, "username": username, "password": "secret1234"},
        ).status_code
        == 201
    )
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": "secret1234"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_attachment_upload_list_download(client, db_session, monkeypatch, tmp_path):
    storage = tmp_path / "att_store"
    monkeypatch.setattr(app_config.settings, "ATTACHMENT_STORAGE_DIR", str(storage), raising=False)

    hdr = _register_and_login(client, "att01@example.com", "att01user")
    p_vid = f"{settings.API_V1_PREFIX}/videos"
    r0 = client.post(p_vid, headers=hdr, json={"title": "带附件的稿", "tag_ids": []})
    assert r0.status_code == 201, r0.text
    vid = r0.json()["id"]

    p_att = f"{settings.API_V1_PREFIX}/videos/{vid}/attachments"
    files = {"file": ("notes.pdf", io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf")}
    r1 = client.post(p_att, headers=hdr, files=files)
    assert r1.status_code == 201, r1.text
    j1 = r1.json()
    assert j1["original_filename"] == "notes.pdf"
    assert j1["size_bytes"] > 0
    aid = j1["id"]

    r2 = client.get(p_att, headers=hdr)
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.headers.get("cache-control", "").lower().find("private") >= 0

    r3 = client.get(f"{p_att}/{aid}/file", headers=hdr)
    assert r3.status_code == 200
    assert b"%PDF" in r3.content
    assert "private" in (r3.headers.get("cache-control") or "").lower()


def test_attachment_rejects_magic_mismatch(client, db_session, monkeypatch, tmp_path):
    storage = tmp_path / "att_magic"
    monkeypatch.setattr(app_config.settings, "ATTACHMENT_STORAGE_DIR", str(storage), raising=False)

    hdr = _register_and_login(client, "att03@example.com", "att03user")
    r0 = client.post(
        f"{settings.API_V1_PREFIX}/videos",
        headers=hdr,
        json={"title": "魔数校验", "tag_ids": []},
    )
    assert r0.status_code == 201
    vid = r0.json()["id"]
    p_att = f"{settings.API_V1_PREFIX}/videos/{vid}/attachments"
    # 伪装成 PDF 的 PNG 文件头
    png_head = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    files = {"file": ("disguise.pdf", io.BytesIO(png_head), "application/pdf")}
    r1 = client.post(p_att, headers=hdr, files=files)
    assert r1.status_code == 400
    assert r1.json().get("code") == UPLOAD_ATTACHMENT_MAGIC_MISMATCH


def test_attachment_rate_limit_per_user(client, db_session, monkeypatch, tmp_path):
    from app.core import attachment_upload_rate_limit

    storage = tmp_path / "att_rl"
    monkeypatch.setattr(app_config.settings, "ATTACHMENT_STORAGE_DIR", str(storage), raising=False)
    monkeypatch.setattr(app_config.settings, "ATTACHMENT_POST_MAX_PER_USER_PER_MINUTE", 2, raising=False)
    attachment_upload_rate_limit.reset_attachment_upload_rate_limit_for_tests()

    hdr = _register_and_login(client, "att04@example.com", "att04user")
    r0 = client.post(
        f"{settings.API_V1_PREFIX}/videos",
        headers=hdr,
        json={"title": "限流", "tag_ids": []},
    )
    assert r0.status_code == 201
    vid = r0.json()["id"]
    p_att = f"{settings.API_V1_PREFIX}/videos/{vid}/attachments"
    pdf = b"%PDF-1.4 rl"
    for _ in range(2):
        r = client.post(p_att, headers=hdr, files={"file": ("a.pdf", io.BytesIO(pdf), "application/pdf")})
        assert r.status_code == 201, r.text
    r3 = client.post(p_att, headers=hdr, files={"file": ("b.pdf", io.BytesIO(pdf), "application/pdf")})
    assert r3.status_code == 429
    assert r3.json().get("code") == UPLOAD_ATTACHMENT_RATE_LIMITED


def test_attachment_rejects_bad_extension(client, db_session, monkeypatch, tmp_path):
    storage = tmp_path / "att2"
    monkeypatch.setattr(app_config.settings, "ATTACHMENT_STORAGE_DIR", str(storage), raising=False)

    hdr = _register_and_login(client, "att02@example.com", "att02user")
    r0 = client.post(
        f"{settings.API_V1_PREFIX}/videos",
        headers=hdr,
        json={"title": "x", "tag_ids": []},
    )
    assert r0.status_code == 201
    vid = r0.json()["id"]
    p_att = f"{settings.API_V1_PREFIX}/videos/{vid}/attachments"
    files = {"file": ("evil.exe", io.BytesIO(b"x"), "application/octet-stream")}
    r1 = client.post(p_att, headers=hdr, files=files)
    assert r1.status_code == 400
    assert r1.json().get("code") == UPLOAD_ATTACHMENT_EXTENSION_NOT_ALLOWED
