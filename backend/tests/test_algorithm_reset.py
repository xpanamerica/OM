from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.algorithm_reset import AlgorithmResetLog, AttentionValueSnapshot, UserAlgorithmPreset, UserAlgorithmState
from app.models.enums import VideoStatus
from app.models.user_follow import UserFollow
from app.models.video import Video
from app.models.video_like import VideoLike
from app.models.view_record import ViewRecord
from app.repositories import algorithm_reset_repository, user_repository


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
    db_session.add(
        UserAlgorithmState(
            user_id=u1,
            mode="custom",
            personalized=True,
            cold_start_strategy="custom_mode",
            algorithm_parameters={"randomness": 5, "diversity": 10, "depth": 90, "entertainment": 10, "challenge": 80, "novelty": 20},
            attention_index=37,
        )
    )
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
    assert body["data"]["parameters"] == state.algorithm_parameters
    assert body["data"]["parameters"] == {"randomness": 95, "diversity": 95, "depth": 45, "entertainment": 50, "challenge": 45, "novelty": 90}
    assert body["data"]["attentionIndex"] == state.attention_index == 37
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
    own_video = Video(
        title="mode own published",
        author_id=user_id,
        status=VideoStatus.PUBLISHED,
        views_count=99,
        likes_count=9,
        favorites_count=3,
    )
    db_session.add(own_video)
    db_session.commit()

    feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 10, "page": 1}, headers=headers)
    assert feed.status_code == 200, feed.text
    payload = feed.json()
    assert payload["algorithmMode"] == "growth"
    assert payload["personalized"] is True
    assert str(own_video.id) in {item["id"] for item in payload["items"]}
    assert "成长模式" in payload["explanation"]
    assert "认知挑战" in payload["items"][0]["recommendation_reason"]
    assert sum(payload["items"][0]["recommendation_reason"].values()) == 100
    assert "为什么推荐你" in payload["items"][0]["recommendation_text"]
    snapshot = db_session.scalar(select(AttentionValueSnapshot).where(AttentionValueSnapshot.user_id == user_id))
    assert snapshot is not None
    assert snapshot.algorithm_mode == "growth"
    assert 0 <= snapshot.time_quality <= 100
    assert 0 <= snapshot.information_value <= 100
    assert 0 <= snapshot.propagation_impact <= 100
    assert 0 <= snapshot.deep_engagement <= 100
    attention = client.get(f"{settings.API_V1_PREFIX}/users/me/attention-index", headers=headers)
    assert attention.status_code == 200, attention.text
    attention_data = attention.json()["data"]
    assert attention_data["attentionIndex"] >= 0
    assert attention_data["formula"] == "Attention Value = 时间质量 × 信息价值 × 传播影响 × 深度参与"
    assert {"timeQuality", "informationValue", "propagationImpact", "deepEngagement"}.issubset(attention_data.keys())
    governance = client.get(f"{settings.API_V1_PREFIX}/users/me/governance-power", headers=headers)
    assert governance.status_code == 200, governance.text
    assert governance.json()["formula"] == "投票权重 = Attention Value（四因子乘法模型）"
    agent = client.get(f"{settings.API_V1_PREFIX}/users/me/ai-agent-panel", headers=headers)
    assert agent.status_code == 200, agent.text
    agent_data = agent.json()
    assert agent_data["modelVersion"] == "agent-v1-rule-based"
    assert agent_data["mode"] == "growth"
    assert agent_data["contentSummary"]
    assert agent_data["attentionOptimization"]
    assert agent_data["learningPathSuggestion"]
    assert {"timeQuality", "informationValue", "propagationImpact", "deepEngagement"}.issubset(agent_data["attentionFactors"].keys())


def test_algorithm_modes_report_factor_based_recommendation_reasons(client, db_session):
    _register(client, "mode-matrix@example.com", "modematrix")
    headers = _login(client, "modematrix")
    for idx in range(5):
        author = user_repository.create_user(
            db_session,
            email=f"matrix-author-{idx}@example.com",
            username=f"matrixauthor{idx}",
            hashed_password=get_password_hash("secret1234"),
        )
        db_session.flush()
        db_session.add(
            Video(
                title=f"matrix video {idx}",
                description="deep note" if idx % 2 else None,
                author_id=author.id,
                status=VideoStatus.PUBLISHED,
                views_count=20 + idx,
                likes_count=idx + 1,
                favorites_count=idx,
                duration_seconds=120 + idx * 90,
            )
        )
    db_session.commit()

    expected_keys = {
        "origin": "随机探索",
        "efficiency": "信息密度",
        "growth": "认知挑战",
        "emotion": "娱乐沉浸",
        "custom": "随机性",
    }
    for mode, key in expected_keys.items():
        patch = client.patch(
            f"{settings.API_V1_PREFIX}/users/me/algorithm-state",
            headers=headers,
            json={
                "mode": mode,
                "parameters": {
                    "randomness": 60,
                    "diversity": 80,
                    "depth": 70,
                    "entertainment": 40,
                    "challenge": 85,
                    "novelty": 75,
                }
                if mode == "custom"
                else None,
            },
        )
        assert patch.status_code == 200, patch.text
        feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 3, "page": 1}, headers=headers)
        assert feed.status_code == 200, feed.text
        item = feed.json()["items"][0]
        reason = item["recommendation_reason"]
        assert key in reason
        assert sum(reason.values()) == 100
        assert item["recommendation_text"].startswith("为什么推荐你：")


def test_custom_algorithm_presets_can_be_saved_applied_and_reset(client, db_session):
    _register(client, "preset-reader@example.com", "presetreader")
    headers = _login(client, "presetreader")
    user_id = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers).json()["id"])
    body = {
        "mode": "custom",
        "parameters": {
            "randomness": 12,
            "diversity": 88,
            "depth": 91,
            "entertainment": 20,
            "challenge": 94,
            "novelty": 76,
        },
    }
    state = client.patch(f"{settings.API_V1_PREFIX}/users/me/algorithm-state", headers=headers, json=body)
    assert state.status_code == 200, state.text

    saved = client.post(
        f"{settings.API_V1_PREFIX}/users/me/algorithm-presets",
        headers=headers,
        json={"name": "Deep Growth", "description": "高深度成长世界模型"},
    )
    assert saved.status_code == 200, saved.text
    preset = saved.json()["data"]
    assert preset["name"] == "Deep Growth"
    assert preset["parameters"]["depth"] == 91
    assert db_session.scalar(select(UserAlgorithmPreset).where(UserAlgorithmPreset.user_id == user_id)) is not None

    reset = client.post(f"{settings.API_V1_PREFIX}/users/me/algorithm-state/reset-custom-defaults", headers=headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["data"]["parameters"]["depth"] == 50

    applied = client.post(
        f"{settings.API_V1_PREFIX}/users/me/algorithm-presets/{preset['id']}/apply",
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["mode"] == "custom"
    assert applied.json()["data"]["parameters"]["depth"] == 91

    listed = client.get(f"{settings.API_V1_PREFIX}/users/me/algorithm-presets", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["name"] == "Deep Growth"


def test_algorithm_preset_save_retries_after_unique_race(client, monkeypatch):
    _register(client, "preset-race@example.com", "presetrace")
    headers = _login(client, "presetrace")
    calls = {"count": 0}
    original = algorithm_reset_repository.upsert_preset

    def flaky_upsert(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise IntegrityError("INSERT user_algorithm_presets", {}, Exception("unique user preset name"))
        return original(*args, **kwargs)

    monkeypatch.setattr(algorithm_reset_repository, "upsert_preset", flaky_upsert)

    saved = client.post(
        f"{settings.API_V1_PREFIX}/users/me/algorithm-presets",
        headers=headers,
        json={"name": "Race Safe", "parameters": {"randomness": 40, "diversity": 80, "depth": 60, "entertainment": 30, "challenge": 70, "novelty": 65}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["name"] == "Race Safe"
    assert calls["count"] == 2


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

    r = client.get(f"{settings.API_V1_PREFIX}/videos", params={"limit": 5}, headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 5
    author_ids = [row["author_id"] for row in rows]
    assert len(set(author_ids)) > 1
    assert str(user_id) in author_ids

    feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 5, "page": 1}, headers=headers)
    assert feed.status_code == 200, feed.text
    payload = feed.json()
    assert payload["algorithmMode"] == "origin"
    assert payload["personalized"] is False
    assert payload["explanation"] == "归源模式已开启：你正在随机、多元地重新探索世界。"
    assert len(payload["items"]) == 5
    assert str(user_id) in [row["author_id"] for row in payload["items"]]


def test_origin_feed_forces_origin_mode_when_personalized_false_is_dirty(client, db_session):
    _register(client, "dirty-origin@example.com", "dirtyorigin")
    headers = _login(client, "dirtyorigin")
    user_id = uuid.UUID(client.get(f"{settings.API_V1_PREFIX}/users/me", headers=headers).json()["id"])
    author = user_repository.create_user(
        db_session,
        email="dirty-origin-author@example.com",
        username="dirtyoriginauthor",
        hashed_password=get_password_hash("secret1234"),
    )
    db_session.flush()
    db_session.add(
        Video(
            title="dirty origin video",
            author_id=author.id,
            status=VideoStatus.PUBLISHED,
            views_count=10,
            likes_count=1,
        )
    )
    db_session.add(
        UserAlgorithmState(
            user_id=user_id,
            mode="efficiency",
            personalized=False,
            cold_start_strategy="random_balanced",
            algorithm_parameters={"randomness": 95, "diversity": 95, "depth": 45, "entertainment": 50, "challenge": 45, "novelty": 90},
        )
    )
    db_session.commit()

    feed = client.get(f"{settings.API_V1_PREFIX}/videos/feed", params={"limit": 1, "page": 1}, headers=headers)
    assert feed.status_code == 200, feed.text
    payload = feed.json()
    assert payload["algorithmMode"] == "origin"
    assert payload["personalized"] is False
    assert "信息密度" not in payload["items"][0]["recommendation_reason"]
