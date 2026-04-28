from __future__ import annotations

import uuid

from app.core.config import settings


def _register(client, email: str, username: str, password: str = "secret1234"):
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert r.status_code == 201, r.text


def _login(client, username: str, password: str = "secret1234") -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _me_id(client, headers: dict[str, str]) -> uuid.UUID:
    r = client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return uuid.UUID(r.json()["id"])


def test_public_profile_and_follow_lists(client, db_session):
    _register(client, "social-a@example.com", "social_a")
    _register(client, "social-b@example.com", "social_b")
    ha = _login(client, "social_a")
    hb = _login(client, "social_b")
    aid = _me_id(client, ha)
    bid = _me_id(client, hb)
    p = f"{settings.API_V1_PREFIX}/users"

    assert client.post(f"{p}/{bid}/follow", headers=ha).status_code == 204
    profile = client.get(f"{p}/{bid}/profile", headers=ha)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["user"]["username"] == "social_b"
    assert body["followers_count"] == 1
    assert body["is_following"] is True
    assert body["follows_me"] is False
    assert body["is_mutual"] is False

    following = client.get(f"{p}/{aid}/following", headers=ha)
    assert following.status_code == 200, following.text
    assert following.json()[0]["username"] == "social_b"
    assert following.json()[0]["is_following"] is True

    followers = client.get(f"{p}/{bid}/followers", headers=hb)
    assert followers.status_code == 200, followers.text
    assert followers.json()[0]["username"] == "social_a"


def test_profile_privacy_mutual_requires_mutual_follow(client, db_session):
    _register(client, "privacy-a@example.com", "privacy_a")
    _register(client, "privacy-b@example.com", "privacy_b")
    ha = _login(client, "privacy_a")
    hb = _login(client, "privacy_b")
    aid = _me_id(client, ha)
    bid = _me_id(client, hb)
    p = f"{settings.API_V1_PREFIX}/users"

    r = client.patch(f"{p}/me/privacy", headers=hb, json={"profile_visibility": "mutual"})
    assert r.status_code == 200, r.text
    assert client.get(f"{p}/{bid}/profile", headers=ha).status_code == 403

    assert client.post(f"{p}/{bid}/follow", headers=ha).status_code == 204
    assert client.get(f"{p}/{bid}/profile", headers=ha).status_code == 403

    assert client.post(f"{p}/{aid}/follow", headers=hb).status_code == 204
    ok = client.get(f"{p}/{bid}/profile", headers=ha)
    assert ok.status_code == 200, ok.text
    assert ok.json()["is_mutual"] is True


def test_direct_messages_respect_message_permission(client, db_session):
    _register(client, "dm-a@example.com", "dm_a")
    _register(client, "dm-b@example.com", "dm_b")
    ha = _login(client, "dm_a")
    hb = _login(client, "dm_b")
    aid = _me_id(client, ha)
    bid = _me_id(client, hb)
    users = f"{settings.API_V1_PREFIX}/users"
    dm = f"{settings.API_V1_PREFIX}/direct-messages"

    r = client.patch(f"{users}/me/privacy", headers=hb, json={"message_permission": "mutual"})
    assert r.status_code == 200, r.text
    assert client.post(f"{dm}/conversations/{bid}/messages", headers=ha, json={"body": "hi"}).status_code == 403

    assert client.post(f"{users}/{bid}/follow", headers=ha).status_code == 204
    assert client.post(f"{dm}/conversations/{bid}/messages", headers=ha, json={"body": "hi"}).status_code == 403

    assert client.post(f"{users}/{aid}/follow", headers=hb).status_code == 204
    sent = client.post(f"{dm}/conversations/{bid}/messages", headers=ha, json={"body": "hi again"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["body"] == "hi again"

    convs = client.get(f"{dm}/conversations", headers=hb)
    assert convs.status_code == 200, convs.text
    assert convs.json()[0]["peer"]["username"] == "dm_a"
    assert convs.json()[0]["unread_count"] == 1

    msgs = client.get(f"{dm}/conversations/{aid}/messages", headers=hb)
    assert msgs.status_code == 200, msgs.text
    assert msgs.json()[0]["body"] == "hi again"
    assert client.get(f"{dm}/conversations", headers=hb).json()[0]["unread_count"] == 0


def test_block_user_cuts_follow_profile_and_messages(client, db_session):
    _register(client, "block-a@example.com", "block_a")
    _register(client, "block-b@example.com", "block_b")
    ha = _login(client, "block_a")
    hb = _login(client, "block_b")
    aid = _me_id(client, ha)
    bid = _me_id(client, hb)
    users = f"{settings.API_V1_PREFIX}/users"
    dm = f"{settings.API_V1_PREFIX}/direct-messages"

    assert client.post(f"{users}/{bid}/follow", headers=ha).status_code == 204
    assert client.post(f"{users}/{aid}/follow", headers=hb).status_code == 204
    assert client.post(f"{users}/{bid}/block", headers=ha).status_code == 204

    blocked = client.get(f"{users}/me/blocked-users", headers=ha)
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()[0]["username"] == "block_b"

    p = client.get(f"{users}/{bid}/profile", headers=ha)
    assert p.status_code == 200, p.text
    assert p.json()["is_blocked"] is True
    assert p.json()["can_message"] is False
    assert client.get(f"{users}/{aid}/profile", headers=hb).status_code == 403
    assert client.post(f"{dm}/conversations/{bid}/messages", headers=ha, json={"body": "no"}).status_code == 403
    assert client.post(f"{users}/{bid}/follow", headers=ha).status_code == 403

    assert client.delete(f"{users}/{bid}/block", headers=ha).status_code == 204
    assert client.get(f"{users}/{bid}/profile", headers=ha).status_code == 200


def test_follow_and_direct_message_create_notifications(client, db_session):
    _register(client, "notif-a@example.com", "notif_a")
    _register(client, "notif-b@example.com", "notif_b")
    ha = _login(client, "notif_a")
    hb = _login(client, "notif_b")
    aid = _me_id(client, ha)
    bid = _me_id(client, hb)
    users = f"{settings.API_V1_PREFIX}/users"
    dm = f"{settings.API_V1_PREFIX}/direct-messages"

    assert client.post(f"{users}/{bid}/follow", headers=ha).status_code == 204
    notes = client.get(f"{users}/me/notifications", headers=hb)
    assert notes.status_code == 200, notes.text
    assert any(x["kind"] == "follow" and "关注了你" in x["title"] for x in notes.json())

    assert client.post(f"{users}/{aid}/follow", headers=hb).status_code == 204
    assert client.post(f"{dm}/conversations/{bid}/messages", headers=ha, json={"body": "ping"}).status_code == 200
    notes2 = client.get(f"{users}/me/notifications", headers=hb)
    assert any(x["kind"] == "direct_message" and x["action_url"] == f"/me/direct-messages/{aid}" for x in notes2.json())
