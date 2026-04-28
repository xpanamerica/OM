from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, inspect, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.algorithm_reset import AttentionValueSnapshot
from app.models.video import Video
from app.models.view_record import ViewRecord
from app.models.user import User
from app.repositories import algorithm_reset_repository
from app.schemas.algorithm_reset import (
    AiAgentPanelOut,
    AlgorithmParameters,
    AlgorithmResetResponse,
    AlgorithmStateOut,
    AlgorithmStateResponse,
    AlgorithmStateUpdate,
    AttentionIndexOut,
    AttentionIndexResponse,
    GovernancePowerOut,
)

RESET_TYPE = "one_click_origin"
MAX_RESETS_PER_24H = 3
ALGORITHM_MODES = {"origin", "efficiency", "growth", "emotion", "custom"}

MODE_DEFAULTS = {
    "origin": AlgorithmParameters(randomness=95, diversity=95, depth=45, entertainment=50, challenge=45, novelty=90),
    "efficiency": AlgorithmParameters(randomness=20, diversity=45, depth=75, entertainment=20, challenge=45, novelty=35),
    "growth": AlgorithmParameters(randomness=45, diversity=80, depth=85, entertainment=25, challenge=90, novelty=75),
    "emotion": AlgorithmParameters(randomness=55, diversity=55, depth=25, entertainment=90, challenge=20, novelty=50),
    "custom": AlgorithmParameters(randomness=50, diversity=70, depth=50, entertainment=50, challenge=50, novelty=60),
}

OPTIONAL_RECOMMENDATION_TABLES = (
    "user_interests",
    "recommendation_weights",
    "content_preferences",
    "recommendation_cache",
    "personalized_feed_history",
    "user_behavior_profile",
    "user_content_scores",
    "algorithm_segments",
    "feed_queue",
    "opaque_recommendation_state",
)

def _delete_user_rows_if_present(db: Session, *, table_name: str, user_id: uuid.UUID) -> bool:
    inspector = inspect(db.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if "user_id" not in columns:
        return False
    db.execute(
        text(f'DELETE FROM "{table_name}" WHERE user_id = :user_id OR user_id = :user_id_hex'),
        {"user_id": str(user_id), "user_id_hex": user_id.hex},
    )
    return True


def _delete_known_recommendation_rows(db: Session, *, user_id: uuid.UUID) -> list[str]:
    db.execute(delete(ViewRecord).where(ViewRecord.user_id == user_id))
    return ["view_records"]


def get_algorithm_state(db: Session, *, user_id: uuid.UUID) -> dict | None:
    row = algorithm_reset_repository.get_state(db, user_id=user_id)
    if row is None:
        return None
    return {
        "mode": row.mode,
        "personalized": row.personalized,
        "resetAt": row.reset_at.isoformat() if row.reset_at else None,
        "explorationSeed": row.exploration_seed,
        "coldStartStrategy": row.cold_start_strategy,
        "parameters": row.algorithm_parameters or MODE_DEFAULTS.get(row.mode, MODE_DEFAULTS["custom"]).model_dump(),
        "attentionIndex": row.attention_index,
    }


def _state_out(row) -> AlgorithmStateOut:
    params = AlgorithmParameters.model_validate(row.algorithm_parameters or MODE_DEFAULTS.get(row.mode, MODE_DEFAULTS["custom"]).model_dump())
    return AlgorithmStateOut(
        mode=row.mode,
        personalized=row.personalized,
        resetAt=row.reset_at,
        explorationSeed=row.exploration_seed,
        coldStartStrategy=row.cold_start_strategy,
        parameters=params,
        attentionIndex=row.attention_index,
    )


def get_or_create_algorithm_state(db: Session, *, user: User) -> AlgorithmStateResponse:
    row = algorithm_reset_repository.get_state(db, user_id=user.id)
    if row is None:
        row = algorithm_reset_repository.upsert_algorithm_state(
            db,
            user_id=user.id,
            mode="efficiency",
            personalized=True,
            cold_start_strategy="value_first",
            algorithm_parameters=MODE_DEFAULTS["efficiency"].model_dump(),
            exploration_seed=str(uuid.uuid4()),
        )
        db.commit()
    return AlgorithmStateResponse(success=True, message="算法模式已同步。", data=_state_out(row))


def update_algorithm_state(db: Session, *, user: User, payload: AlgorithmStateUpdate) -> AlgorithmStateResponse:
    mode = payload.mode
    if mode not in ALGORITHM_MODES:
        raise AppError("不支持的算法模式", status_code=400, code="ALGORITHM_MODE_INVALID")
    params = payload.parameters or MODE_DEFAULTS[mode]
    row = algorithm_reset_repository.upsert_algorithm_state(
        db,
        user_id=user.id,
        mode=mode,
        personalized=mode != "origin",
        cold_start_strategy="random_balanced" if mode == "origin" else f"{mode}_mode",
        algorithm_parameters=params.model_dump(),
        exploration_seed=str(uuid.uuid4()) if mode == "origin" else None,
    )
    db.commit()
    return AlgorithmStateResponse(success=True, message="算法模式已更新。", data=_state_out(row))


def recommendation_reason_for_video(*, mode: str, video: Video) -> tuple[dict[str, int], str]:
    if mode == "origin":
        reason = {"随机探索": 50, "内容质量": 30, "时间新鲜度": 20}
    elif mode == "efficiency":
        reason = {"信息密度": 42, "学习价值": 28, "时间新鲜度": 20, "随机校准": 10}
    elif mode == "growth":
        reason = {"认知挑战": 38, "内容深度": 26, "新颖性": 20, "质量评分": 16}
    elif mode == "emotion":
        reason = {"娱乐沉浸": 42, "时间新鲜度": 20, "随机探索": 25, "质量评分": 13}
    elif mode == "custom":
        reason = {"你的自定义参数": 70, "内容质量": 12, "新颖探索": 18}
    else:
        reason = {"综合质量": 50, "时间新鲜度": 30, "基础探索": 20}
    text = "为什么推荐你：" + "，".join(f"{key} {value}%" for key, value in reason.items())
    return reason, text


def record_attention_snapshot(db: Session, *, user: User | None, mode: str, videos: list[Video]) -> None:
    if user is None or not videos:
        return
    quality = sum(min(v.views_count + v.likes_count * 4 + v.favorites_count * 6, 1000) for v in videos) / max(len(videos), 1)
    diversity = len({v.author_id for v in videos}) / max(len(videos), 1)
    depth = sum(1 for v in videos if (v.description or "").strip() or (v.duration_seconds or 0) >= 180) / max(len(videos), 1)
    input_quality = int(min(100, quality / 10))
    output_value = int(min(100, (sum(v.likes_count + v.favorites_count for v in videos) / max(len(videos), 1)) * 8))
    cognitive_growth = int(min(100, diversity * 45 + depth * 55))
    attention_index = int(input_quality * 0.4 + output_value * 0.25 + cognitive_growth * 0.35)
    row = AttentionValueSnapshot(
        user_id=user.id,
        algorithm_mode=mode,
        input_quality=input_quality,
        output_value=output_value,
        cognitive_growth=cognitive_growth,
        attention_index=attention_index,
        detail={"items": len(videos), "authorDiversity": diversity, "depthRatio": depth},
    )
    db.add(row)
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    if state is not None:
        state.attention_index = max(state.attention_index, attention_index)
        db.add(state)
    db.flush()


def get_attention_index(db: Session, *, user: User) -> AttentionIndexResponse:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    attention = state.attention_index if state is not None else 0
    return AttentionIndexResponse(
        success=True,
        data=AttentionIndexOut(
            attentionIndex=attention,
            inputQuality=min(100, attention),
            outputValue=max(0, attention - 8),
            cognitiveGrowth=min(100, attention + 6),
            latestMode=state.mode if state is not None else None,
            explanation="Attention Index = 输入质量 x 40% + 输出价值 x 25% + 认知提升 x 35%。",
        ),
    )


def get_ai_agent_panel(db: Session, *, user: User) -> AiAgentPanelOut:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    mode = state.mode if state is not None else "efficiency"
    return AiAgentPanelOut(
        summary=f"你的 AI Agent 当前围绕「{mode}」模式优化内容筛选。",
        suggestions=["优先收藏高价值内容，提升输出价值。", "每周切换一次成长模式，拓展认知边界。", "当连续浏览低深度内容时，尝试提高深度或认知挑战参数。"],
        nextActions=["查看为什么推荐你", "调整自定义算法参数", "生成一条学习路径建议"],
    )


def get_governance_power(db: Session, *, user: User) -> GovernancePowerOut:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    power = state.attention_index if state is not None else 0
    return GovernancePowerOut(votingPower=power, formula="投票权重 = Attention Value", canVote=power > 0)


def is_origin_mode(db: Session, *, user_id: uuid.UUID) -> bool:
    state = get_algorithm_state(db, user_id=user_id)
    if not state:
        return False
    return state.get("mode") == "origin" or state.get("personalized") is False


def reset_to_origin(
    db: Session,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> AlgorithmResetResponse:
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)
    recent_count = algorithm_reset_repository.count_successful_resets_since(
        db,
        user_id=user.id,
        since=since,
        reset_type=RESET_TYPE,
    )
    if recent_count >= MAX_RESETS_PER_24H:
        raise AppError("一键归源过于频繁，请 24 小时后再试", status_code=429, code="ALGORITHM_RESET_RATE_LIMITED")

    exploration_seed = str(uuid.uuid4())
    affected_tables: list[str] = []

    try:
        affected_tables.extend(_delete_known_recommendation_rows(db, user_id=user.id))
        for table_name in OPTIONAL_RECOMMENDATION_TABLES:
            if _delete_user_rows_if_present(db, table_name=table_name, user_id=user.id):
                affected_tables.append(table_name)
        algorithm_reset_repository.upsert_origin_state(
            db,
            user_id=user.id,
            reset_at=now,
            exploration_seed=exploration_seed,
        )
        affected_tables.append("user_algorithm_states")
        algorithm_reset_repository.create_log(
            db,
            user_id=user.id,
            reset_at=now,
            reset_type=RESET_TYPE,
            ip_address=ip_address,
            user_agent=user_agent,
            affected_tables=affected_tables,
            status="success",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return AlgorithmResetResponse(
        success=True,
        message="你已归源。系统将不再基于旧画像推送内容。",
        data=AlgorithmStateOut(
            mode="origin",
            personalized=False,
            resetAt=now,
            explorationSeed=exploration_seed,
            coldStartStrategy="random_balanced",
        ),
    )
