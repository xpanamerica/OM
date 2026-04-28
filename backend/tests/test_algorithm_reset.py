from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.algorithm_reset import AlgorithmResetLog, AttentionValueSnapshot, UserAlgorithmState
from app.models.enums import VideoStatus
from app.models.user_follow import UserFollow
from app.models.video import Video
from app.models.video_like import VideoLike
from app.models.view_record import ViewRecord
from app.repositories import user_repository


def _register(client, email: str, username: str) -> None:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": email, "username": username, "password": "secret1234"},
    )
    assert r.status_code == 201, r.text


def _login(client, username: str) -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": username, "password": "secret1234"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_algorithm_reset_requires_auth(client):
    r = client.post(f"{settings.API_V1_PREFIX}/users/me/algorithm-reset")
    assert r.status_code == 401


def test_algorithm_reset_clears_recommendation_state_but_keeps_core_data(client, db_session):
    _register(client, "reset1@example.com", "resetuser1")
    _register(client, "reset2@example.com", "resetuser2")
    h1 = _login(client, "resetuser1")
    h2 = _login(client, "resetuser2")
    u1 = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=h1).json()["id"])
    u2 = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=h2).json()["id"])
    video = Video(title="published", author_id=u2, status=VideoStatus.PUBLISHED)
    db_session.add(video)
    db_session.flush()
    db_session.add(ViewRecord(user_id=u1, video_id=video.id, progress_seconds=12))
    db_session.add(VideoLike(user_id=u1, video_id=video.id))
    db_session.add(UserFollow(follower_id=u1, followee_id=u2))
    db_session.commit()

    r = client.post(
        f"{settings.API_V1_PREFIX}/users/me/algorithm-reset",
        headers={**h1, "user-agent": "pytest-agent", "x-forwarded-for": "203.0.113.10"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["data"]["mode"] == "origin"
    assert body["data"]["personalized"] is False
    assert body["data"]["coldStartStrategy"] == "random_balanced"
    assert body["data"]["explorationSeed"]

    assert db_session.scalar(select(ViewRecord).where(ViewRecord.user_id == u1)) is None
    assert db_session.scalar(select(VideoLike).where(VideoLike.user_id == u1)) is not None
    assert db_session.scalar(select(UserFollow).where(UserFollow.follower_id == u1)) is not None

    state = db_session.scalar(select(UserAlgorithmState).where(UserAlgorithmState.user_id == u1))
    assert state is not None
    assert state.mode == "origin"
    assert state.personalized is False
    assert state.cold_start_strategy == "random_balanced"
    assert state.exploration_seed == body["data"]["explorationSeed"]
    log = db_session.scalar(select(AlgorithmResetLog).where(AlgorithmResetLog.user_id == u1))
    assert log is not None
    assert log.reset_type == "one_click_origin"
    assert log.status == "success"
    assert "view_records" in log.affected_tables
    assert log.ip_address == "203.0.113.10"
    assert log.user_agent == "pytest-agent"
    assert log.error_message is None


def test_algorithm_reset_rate_limit_three_per_24h(client, db_session):
    _register(client, "reset3@example.com", "resetuser3")
    headers = _login(client, "resetuser3")
    user_id = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers).json()["id"])
    now = datetime.now(UTC)
    for i in range(3):
        db_session.add(
            AlgorithmResetLog(
                user_id=user_id,
                reset_at=now - timedelta(hours=i),
                reset_type="one_click_origin",
                affected_tables=[],
                status="success",
            )
        )
    db_session.commit()

    r = client.post(f"{settings.API_V1_PREFIX}/users/me/algorithm-reset", headers=headers)
    assert r.status_code == 429, r.text


def test_algorithm_mode_can_be_switched_and_feed_reports_mode(client, db_session):
    _register(client, "mode-reader@example.com", "modereader")
    headers = _login(client, "modereader")
    user_id = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers).json()["id"])
    for idx in range(3):
        author = user_repository.create_user(
            db_session,
            email=f"mode-author-{idx}@example.com",
            username=f"modeauthor{idx}",
            hashed_password=get_password_hash("secret1234"),
        )
        db_session.flush()
        db_session.add(Video(title=f"mode video {idx}", author_id=author.id, status=VideoStatus.PUBLISHED, views_count=idx + 1))
    db_session.commit()

    r = client.patch(
        f"{settings.API_V1_PREFIX}/users/me/algorithm-state",
        headers=headers,
        json={"mode": "growth"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["mode"] == "growth"
    assert body["data"]["personalized"] is True
    state = db_session.scalar(select(UserAlgorithmState).where(UserAlgorithmState.user_id == user_id))
    assert state is not None
    assert state.mode == "growth"
    assert state.algorithm_parameters["challenge"] == 90

    feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 3, "page": 1}, headers=headers)
    assert feed.status_code == 200, feed.text
    payload = feed.json()
    assert payload["algorithmMode"] == "growth"
    assert payload["personalized"] is True
    assert "成长模式" in payload["explanation"]
    assert payload["items"][0]["recommendation_reason"]["认知挑战"] == 38
    assert "为什么推荐你" in payload["items"][0]["recommendation_text"]
    snapshot = db_session.scalar(select(AttentionValueSnapshot).where(AttentionValueSnapshot.user_id == user_id))
    assert snapshot is not None
    assert snapshot.algorithm_mode == "growth"
    attention = client.get(f"{settings.API_V1_PREFIX}/users/me/attention-index", headers=headers)
    assert attention.status_code == 200, attention.text
    assert attention.json()["data"]["attentionIndex"] >= 0
    governance = client.get(f"{settings.API_V1_PREFIX}/users/me/governance-power", headers=headers)
    assert governance.status_code == 200, governance.text
    assert governance.json()["formula"] == "投票权重 = Attention Value"


def test_origin_mode_feed_uses_balanced_non_follow_only_strategy(client, db_session):
    _register(client, "origin-reader@example.com", "originreader")
    headers = _login(client, "originreader")
    user_id = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers).json()["id"])
    for idx in range(4):
        author = user_repository.create_user(
            db_session,
            email=f"origin-author-{idx}@example.com",
            username=f"originauthor{idx}",
            hashed_password=get_password_hash("secret1234"),
        )
        db_session.flush()
        db_session.add(
            Video(
                title=f"origin video {idx}",
                author_id=author.id,
                status=VideoStatus.PUBLISHED,
                views_count=idx * 10,
                likes_count=idx,
            )
        )
    db_session.commit()
    db_session.add(Video(title="reader own video", author_id=user_id, status=VideoStatus.PUBLISHED))
    db_session.commit()
    reset = client.post(f"{settings.API_V1_PREFIX}/users/me/algorithm-reset", headers=headers)
    assert reset.status_code == 200, reset.text
    state = db_session.scalar(select(UserAlgorithmState).where(UserAlgorithmState.user_id == user_id))
    assert state is not None

    r = client.get(f"{settings.API_V1_PREFIX}/videos", params={"limit": 4}, headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 4
    author_ids = [row["author_id"] for row in rows]
    assert len(set(author_ids)) > 1
    assert str(user_id) not in author_ids

    feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 4, "page": 1}, headers=headers)
    assert feed.status_code == 200, feed.text
    payload = feed.json()
    assert payload["algorithmMode"] == "origin"
    assert payload["personalized"] is False
    assert payload["explanation"] == "归源模式已开启：你正在随机、多元地重新探索世界。"
    assert len(payload["items"]) == 4
    assert str(user_id) not in [row["author_id"] for row in payload["items"]]
