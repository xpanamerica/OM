"""用户站内消息 API。"""

from __future__ import annotations

from app.core.config import settings


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


def test_notifications_unread_and_list_and_read(client):
    p = f"{settings.API_V1_PREFIX}/users"
    _register(client, "un1@example.com", "un1user")
    hdr = _login(client, "un1user")

    r0 = client.get(f"{p}/me/notifications/unread-count", headers=hdr)
    assert r0.status_code == 200, r0.text
    assert r0.json()["unread_count"] >= 1

    r1 = client.get(f"{p}/me/notifications", headers=hdr, params={"offset": 0, "limit": 20})
    assert r1.status_code == 200, r1.text
    assert int(r1.headers.get("X-Total-Count", "0")) >= 1
    items = r1.json()
    assert isinstance(items, list) and len(items) >= 1
    nid = items[0]["id"]

    r2 = client.patch(f"{p}/me/notifications/{nid}/read", headers=hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["read_at"] is not None

    r3 = client.post(f"{p}/me/notifications/read-all", headers=hdr)
    assert r3.status_code == 200, r3.text
    assert r3.json()["marked"] >= 0
