from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.algorithm_reset import AlgorithmResetLog, UserAlgorithmState


def get_state(db: Session, *, user_id: uuid.UUID) -> UserAlgorithmState | None:
    stmt = select(UserAlgorithmState).where(UserAlgorithmState.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert_origin_state(
    db: Session,
    *,
    user_id: uuid.UUID,
    reset_at: datetime,
    exploration_seed: str,
) -> UserAlgorithmState:
    row = get_state(db, user_id=user_id)
    if row is None:
        row = UserAlgorithmState(user_id=user_id)
    row.mode = "origin"
    row.personalized = False
    row.reset_at = reset_at
    row.exploration_seed = exploration_seed
    row.cold_start_strategy = "random_balanced"
    row.algorithm_parameters = {
        "randomness": 95,
        "diversity": 95,
        "depth": 45,
        "entertainment": 50,
        "challenge": 45,
        "novelty": 90,
    }
    db.add(row)
    db.flush()
    return row


def upsert_algorithm_state(
    db: Session,
    *,
    user_id: uuid.UUID,
    mode: str,
    personalized: bool,
    cold_start_strategy: str,
    algorithm_parameters: dict,
    exploration_seed: str | None = None,
) -> UserAlgorithmState:
    row = get_state(db, user_id=user_id)
    if row is None:
        row = UserAlgorithmState(user_id=user_id)
    row.mode = mode
    row.personalized = personalized
    row.cold_start_strategy = cold_start_strategy
    row.algorithm_parameters = algorithm_parameters
    if exploration_seed:
        row.exploration_seed = exploration_seed
    db.add(row)
    db.flush()
    return row


def count_successful_resets_since(
    db: Session,
    *,
    user_id: uuid.UUID,
    since: datetime,
    reset_type: str = "one_click_origin",
) -> int:
    stmt = (
        select(func.count(AlgorithmResetLog.id))
        .where(
            AlgorithmResetLog.user_id == user_id,
            AlgorithmResetLog.reset_type == reset_type,
            AlgorithmResetLog.status == "success",
            AlgorithmResetLog.reset_at >= since,
        )
    )
    return int(db.execute(stmt).scalar_one())


def create_log(
    db: Session,
    *,
    user_id: uuid.UUID,
    reset_at: datetime,
    reset_type: str,
    ip_address: str | None,
    user_agent: str | None,
    affected_tables: list[str],
    status: str,
    error_message: str | None = None,
) -> AlgorithmResetLog:
    row = AlgorithmResetLog(
        user_id=user_id,
        reset_at=reset_at,
        reset_type=reset_type,
        ip_address=ip_address,
        user_agent=user_agent,
        affected_tables=affected_tables,
        status=status,
        error_message=error_message,
    )
    db.add(row)
    db.flush()
    return row
