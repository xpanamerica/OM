from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.algorithm_reset import AttentionValueSnapshot
from app.models.video import Video
from app.models.view_record import ViewRecord
from app.models.user import User
from app.repositories import algorithm_reset_repository
from app.schemas.algorithm_reset import (
    ATTENTION_VALUE_FORMULA,
    AiAgentPanelOut,
    AlgorithmParameters,
    AlgorithmPresetCreate,
    AlgorithmPresetListResponse,
    AlgorithmPresetOut,
    AlgorithmPresetResponse,
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


def _preset_out(row) -> AlgorithmPresetOut:
    return AlgorithmPresetOut(
        id=row.id,
        name=row.name,
        description=row.description,
        parameters=AlgorithmParameters.model_validate(row.parameters),
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


def list_algorithm_presets(db: Session, *, user: User) -> AlgorithmPresetListResponse:
    rows = algorithm_reset_repository.list_presets(db, user_id=user.id)
    return AlgorithmPresetListResponse(success=True, items=[_preset_out(row) for row in rows])


def save_algorithm_preset(db: Session, *, user: User, payload: AlgorithmPresetCreate) -> AlgorithmPresetResponse:
    name = payload.name.strip()
    if not name:
        raise AppError("模板名称不能为空", status_code=400, code="ALGORITHM_PRESET_NAME_EMPTY")
    current = algorithm_reset_repository.get_state(db, user_id=user.id)
    parameters = payload.parameters
    if parameters is None:
        if current is None:
            parameters = MODE_DEFAULTS["custom"]
        else:
            parameters = AlgorithmParameters.model_validate(
                current.algorithm_parameters or MODE_DEFAULTS.get(current.mode, MODE_DEFAULTS["custom"]).model_dump()
            )
    description = payload.description.strip() if payload.description else None
    params = parameters.model_dump()
    try:
        row = algorithm_reset_repository.upsert_preset(
            db,
            user_id=user.id,
            name=name,
            description=description,
            parameters=params,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        try:
            row = algorithm_reset_repository.upsert_preset(
                db,
                user_id=user.id,
                name=name,
                description=description,
                parameters=params,
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AppError(
                "同名世界模型模板正在被保存，请稍后重试",
                status_code=409,
                code="ALGORITHM_PRESET_NAME_CONFLICT",
            ) from exc
    return AlgorithmPresetResponse(success=True, message="世界模型模板已保存。", data=_preset_out(row))


def apply_algorithm_preset(db: Session, *, user: User, preset_id: uuid.UUID) -> AlgorithmStateResponse:
    preset = algorithm_reset_repository.get_preset(db, preset_id=preset_id, user_id=user.id)
    if preset is None:
        raise AppError("算法模板不存在", status_code=404, code="ALGORITHM_PRESET_NOT_FOUND")
    row = algorithm_reset_repository.upsert_algorithm_state(
        db,
        user_id=user.id,
        mode="custom",
        personalized=True,
        cold_start_strategy="custom_mode",
        algorithm_parameters=AlgorithmParameters.model_validate(preset.parameters).model_dump(),
    )
    db.commit()
    return AlgorithmStateResponse(success=True, message="世界模型模板已应用。", data=_state_out(row))


def reset_custom_parameters_to_default(db: Session, *, user: User) -> AlgorithmStateResponse:
    row = algorithm_reset_repository.upsert_algorithm_state(
        db,
        user_id=user.id,
        mode="custom",
        personalized=True,
        cold_start_strategy="custom_mode",
        algorithm_parameters=MODE_DEFAULTS["custom"].model_dump(),
    )
    db.commit()
    return AlgorithmStateResponse(success=True, message="自定义参数已恢复默认。", data=_state_out(row))


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


def _clamp_score(value: float) -> int:
    return int(max(0, min(round(value), 100)))


def _latest_attention_snapshot(db: Session, *, user_id: uuid.UUID) -> AttentionValueSnapshot | None:
    stmt = (
        select(AttentionValueSnapshot)
        .where(AttentionValueSnapshot.user_id == user_id)
        .order_by(desc(AttentionValueSnapshot.created_at), desc(AttentionValueSnapshot.id))
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def record_attention_snapshot(db: Session, *, user: User | None, mode: str, videos: list[Video]) -> None:
    if user is None or not videos:
        return
    count = max(len(videos), 1)
    quality = sum(min(v.views_count + v.likes_count * 4 + v.favorites_count * 6, 1000) for v in videos) / count
    diversity = len({v.author_id for v in videos}) / count
    depth = sum(1 for v in videos if (v.description or "").strip() or (v.duration_seconds or 0) >= 180) / count
    completion_proxy = sum(min((v.duration_seconds or 120) / 300, 1.0) for v in videos) / count
    engagement_ratio = (
        sum((v.likes_count + v.favorites_count * 2 + int(getattr(v, "comments_count", 0)) * 3) / max(v.views_count + 1, 1) for v in videos)
        / count
    )
    share_proxy = (
        sum(min((v.favorites_count + int(getattr(v, "comments_count", 0))) / max(v.views_count + 1, 1), 1.0) for v in videos)
        / count
    )
    time_quality = _clamp_score(completion_proxy * 55 + depth * 25 + diversity * 20)
    information_value = _clamp_score(min(quality / 10, 100) * 0.55 + depth * 30 + diversity * 15)
    propagation_impact = _clamp_score(min(engagement_ratio * 180, 100) * 0.65 + min(share_proxy * 200, 100) * 0.35)
    deep_engagement = _clamp_score(depth * 45 + min(engagement_ratio * 160, 100) * 0.35 + diversity * 20)
    input_quality = _clamp_score((time_quality + information_value + diversity * 100) / 3)
    output_value = propagation_impact
    cognitive_growth = _clamp_score((information_value * 0.45) + (deep_engagement * 0.55))
    attention_index = _clamp_score(
        (time_quality / 100)
        * (information_value / 100)
        * (max(propagation_impact, 1) / 100)
        * (deep_engagement / 100)
        * 100
    )
    row = AttentionValueSnapshot(
        user_id=user.id,
        algorithm_mode=mode,
        input_quality=input_quality,
        output_value=output_value,
        cognitive_growth=cognitive_growth,
        time_quality=time_quality,
        information_value=information_value,
        propagation_impact=propagation_impact,
        deep_engagement=deep_engagement,
        attention_index=attention_index,
        detail={
            "items": len(videos),
            "authorDiversity": round(diversity, 4),
            "depthRatio": round(depth, 4),
            "completionProxy": round(completion_proxy, 4),
            "engagementRatio": round(engagement_ratio, 4),
            "shareProxy": round(share_proxy, 4),
            "formula": ATTENTION_VALUE_FORMULA,
        },
    )
    db.add(row)
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    if state is not None:
        state.attention_index = max(state.attention_index, attention_index)
        db.add(state)
    db.flush()


def get_attention_index(db: Session, *, user: User) -> AttentionIndexResponse:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    latest = _latest_attention_snapshot(db, user_id=user.id)
    attention = latest.attention_index if latest is not None else (state.attention_index if state is not None else 0)
    return AttentionIndexResponse(
        success=True,
        data=AttentionIndexOut(
            attentionIndex=attention,
            inputQuality=latest.input_quality if latest is not None else min(100, attention),
            outputValue=latest.output_value if latest is not None else max(0, attention - 8),
            cognitiveGrowth=latest.cognitive_growth if latest is not None else min(100, attention + 6),
            timeQuality=latest.time_quality if latest is not None else 0,
            informationValue=latest.information_value if latest is not None else 0,
            propagationImpact=latest.propagation_impact if latest is not None else 0,
            deepEngagement=latest.deep_engagement if latest is not None else 0,
            formula=ATTENTION_VALUE_FORMULA,
            detail=latest.detail if latest is not None else None,
            latestMode=latest.algorithm_mode if latest is not None else (state.mode if state is not None else None),
            explanation="Attention Index 使用乘法模型：时间质量 × 信息价值 × 传播影响 × 深度参与；任一维度过低都会拉低最终指数。",
        ),
    )


def get_ai_agent_panel(db: Session, *, user: User) -> AiAgentPanelOut:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    mode = state.mode if state is not None else "efficiency"
    latest = _latest_attention_snapshot(db, user_id=user.id)
    params = AlgorithmParameters.model_validate(
        state.algorithm_parameters if state is not None and state.algorithm_parameters else MODE_DEFAULTS.get(mode, MODE_DEFAULTS["custom"]).model_dump()
    )
    factors = {
        "timeQuality": latest.time_quality if latest is not None else 0,
        "informationValue": latest.information_value if latest is not None else 0,
        "propagationImpact": latest.propagation_impact if latest is not None else 0,
        "deepEngagement": latest.deep_engagement if latest is not None else 0,
    }
    weakest_key = min(factors, key=factors.get) if latest is not None else "timeQuality"
    factor_names = {
        "timeQuality": "时间质量",
        "informationValue": "信息价值",
        "propagationImpact": "传播影响",
        "deepEngagement": "深度参与",
    }
    mode_names = {
        "origin": "归源模式",
        "efficiency": "效率模式",
        "growth": "成长模式",
        "emotion": "情绪模式",
        "custom": "自定义模式",
    }
    alerts: list[str] = []
    if latest is None:
        alerts.append("还没有足够的观看样本，先浏览一组推荐内容以生成真实注意力画像。")
    elif factors[weakest_key] < 35:
        alerts.append(f"{factor_names[weakest_key]}偏低，建议先补齐这一维度，否则 Attention Index 会被乘法模型拉低。")
    if mode == "emotion" and params.entertainment >= 80 and params.depth <= 30:
        alerts.append("娱乐性很高但深度较低，适合放松，但不建议长时间作为默认世界模型。")
    if mode == "growth" and params.challenge >= 85:
        alerts.append("成长模式挑战强度较高，建议搭配收藏和笔记，否则高挑战内容容易流失价值。")

    learning_path = {
        "origin": "先连续探索 6-10 条不同作者内容，再把真正有价值的主题保存成自定义模板。",
        "efficiency": "按“高信息密度内容 -> 收藏 -> 复盘输出”建立短链路学习路径。",
        "growth": "选择一个陌生但高价值主题，连续观看 3 条深度内容，再写下一个反常识结论。",
        "emotion": "把情绪模式限定为短时恢复区，结束后切回效率或成长模式承接长期目标。",
        "custom": "围绕当前世界模型做一轮 A/B 调参：每次只调整一个参数并观察 Attention 四因子变化。",
    }.get(mode, "先建立明确目标，再选择匹配的算法模式。")
    optimization = (
        f"当前最需要优化的是「{factor_names[weakest_key]}」。"
        if latest is not None
        else "当前样本不足，AI Agent 暂不做强判断。"
    )
    suggestions = [
        optimization,
        "保留高价值内容的收藏或评论行为，系统会把它视为更强的深度参与信号。",
        f"当前模式为{mode_names.get(mode, mode)}，可根据目标切换到更匹配的算法模式。",
    ]
    if mode == "custom":
        suggestions.append(f"你的自定义世界模型：随机 {params.randomness}、多样 {params.diversity}、深度 {params.depth}、娱乐 {params.entertainment}、挑战 {params.challenge}、新颖 {params.novelty}。")
    return AiAgentPanelOut(
        mode=mode,
        summary=f"你的 AI Agent 当前围绕「{mode_names.get(mode, mode)}」进行注意力优化。",
        contentSummary=(
            f"最近一次推荐样本的 Attention Index 为 {latest.attention_index}，"
            f"四因子分别是时间质量 {factors['timeQuality']}、信息价值 {factors['informationValue']}、"
            f"传播影响 {factors['propagationImpact']}、深度参与 {factors['deepEngagement']}。"
            if latest is not None
            else "还没有生成 Attention 快照，Agent 会先等待你的真实浏览行为。"
        ),
        attentionOptimization=optimization,
        learningPathSuggestion=learning_path,
        alerts=alerts,
        attentionFactors=factors,
        suggestions=suggestions,
        nextActions=["查看为什么推荐你", "调整自定义算法参数", "保存当前世界模型模板", "按建议生成一条学习路径"],
    )


def get_governance_power(db: Session, *, user: User) -> GovernancePowerOut:
    state = algorithm_reset_repository.get_state(db, user_id=user.id)
    power = state.attention_index if state is not None else 0
    return GovernancePowerOut(votingPower=power, formula="投票权重 = Attention Value（四因子乘法模型）", canVote=power > 0)


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
        state_row = algorithm_reset_repository.upsert_origin_state(
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
        data=_state_out(state_row),
    )