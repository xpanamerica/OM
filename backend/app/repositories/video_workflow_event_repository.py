from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, insert, literal_column, or_, select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.workflow_audit_log import (
    log_workflow_audit_appended,
    log_workflow_audit_pg_sequence_misconfigured,
    log_workflow_audit_sequence_exhausted,
    log_workflow_audit_sequence_retry,
)
from app.domain.video_workflow_rules import WorkflowPostKind
from app.models.video_workflow_event import VideoWorkflowEvent

# 与 alembic/versions/0014_workflow_audit_sequence_pg_seq.py 中序列名一致
_PG_AUDIT_SEQUENCE = "sq_video_workflow_events_audit_seq"

# 与 WorkflowPostKind 值一致（测试与调用方可继续用模块级常量）
ACTION_SUBMIT_REVIEW = WorkflowPostKind.SUBMIT_REVIEW.value
ACTION_APPROVE = WorkflowPostKind.APPROVE.value
ACTION_REJECT = WorkflowPostKind.REJECT.value
ACTION_OFFLINE_ADMIN = WorkflowPostKind.OFFLINE_ADMIN.value


def count_for_video(db: Session, *, video_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(VideoWorkflowEvent).where(VideoWorkflowEvent.video_id == video_id)
        )
        or 0
    )


def list_page_by_video_id(
    db: Session,
    *,
    video_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[VideoWorkflowEvent], int]:
    """偏移分页 + 窗口函数总数（有行时一次查询；空页时补 count）。"""
    _total = func.count().over().label("_audit_total")
    stmt = (
        select(VideoWorkflowEvent, _total)
        .where(VideoWorkflowEvent.video_id == video_id)
        .order_by(VideoWorkflowEvent.created_at.asc(), VideoWorkflowEvent.audit_sequence.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return [], count_for_video(db, video_id=video_id)
    events = [r[0] for r in rows]
    total = int(rows[0][1])
    return events, total


def _bind_created_at_for_compare(db: Session, dt: datetime) -> datetime:
    """SQLite 常存无时区时间戳；与列比较时绑定 naive UTC，避免与 aware 参数比较不到行。"""
    if dt.tzinfo is None:
        return dt
    utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
    if db.get_bind().dialect.name == "sqlite":
        return utc
    return dt


def list_after_cursor(
    db: Session,
    *,
    video_id: uuid.UUID,
    after_created_at: datetime,
    after_audit_sequence: int,
    limit: int,
) -> list[VideoWorkflowEvent]:
    """键集续页：严格晚于 `(after_created_at, after_audit_sequence)`（与 `encode_workflow_audit_cursor` 一致）。"""
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        # SQLite 常存 CURRENT_TIMESTAMP 秒精度文本；DateTime 绑定会带 .000000，直接 ==/> 比不到行。
        ac = _bind_created_at_for_compare(db, after_created_at)
        anchor_s = ac.strftime("%Y-%m-%d %H:%M:%S")
        ts_key = func.strftime("%Y-%m-%d %H:%M:%S", VideoWorkflowEvent.created_at)
        cond = or_(
            ts_key > anchor_s,
            and_(ts_key == anchor_s, VideoWorkflowEvent.audit_sequence > after_audit_sequence),
        )
    else:
        ac = _bind_created_at_for_compare(db, after_created_at)
        cond = or_(
            VideoWorkflowEvent.created_at > ac,
            and_(VideoWorkflowEvent.created_at == ac, VideoWorkflowEvent.audit_sequence > after_audit_sequence),
        )
    stmt = (
        select(VideoWorkflowEvent)
        .where(VideoWorkflowEvent.video_id == video_id)
        .where(cond)
        .order_by(VideoWorkflowEvent.created_at.asc(), VideoWorkflowEvent.audit_sequence.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _next_global_audit_sequence(db: Session) -> int:
    cur = db.scalar(select(func.coalesce(func.max(VideoWorkflowEvent.audit_sequence), 0)))
    return int(cur or 0) + 1


def _is_audit_sequence_unique_violation(exc: IntegrityError) -> bool:
    """并发下 `MAX+1` 可能撞唯一约束；仅本表 audit_sequence 冲突可安全重试。"""
    orig = getattr(exc, "orig", exc)
    msg = str(orig).lower()
    if "uq_video_workflow_events_audit_sequence" in msg:
        return True
    if "audit_sequence" not in msg:
        return False
    if "video_workflow_events" not in msg and "uq_video_workflow" not in msg:
        return False
    return "unique" in msg or "duplicate key" in msg


_APPEND_EVENT_MAX_ATTEMPTS = 32


def append_event(
    db: Session,
    *,
    video_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    from_status: str,
    to_status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """追加审计行。

    PostgreSQL：优先使用数据库 ``SEQUENCE``（迁移 0014），插入无 MAX+1 竞态。
    其它方言：``MAX+1`` + SAVEPOINT 下撞 ``audit_sequence`` 唯一约束时重试。
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        _append_event_postgresql(
            db,
            video_id=video_id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            detail=detail,
        )
        return

    _append_event_application_sequence(
        db,
        video_id=video_id,
        actor_id=actor_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        detail=detail,
    )


def _append_event_postgresql(
    db: Session,
    *,
    video_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    from_status: str,
    to_status: str,
    detail: dict[str, Any] | None,
) -> None:
    """使用 ``nextval`` 插入（须已执行迁移 0014）。"""
    nid = uuid.uuid4()
    stmt = (
        insert(VideoWorkflowEvent)
        .values(
            id=nid,
            video_id=video_id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            detail=detail,
            audit_sequence=literal_column(f"nextval('{_PG_AUDIT_SEQUENCE}')"),
        )
        .returning(VideoWorkflowEvent.audit_sequence)
    )
    try:
        row = db.execute(stmt).one()
    except ProgrammingError as e:
        log_workflow_audit_pg_sequence_misconfigured(e)
        raise RuntimeError(
            "PostgreSQL 工作流审计写入失败：请确认已执行 Alembic 迁移 "
            "`0014_workflow_audit_sequence_pg_seq`（为 audit_sequence 创建 SEQUENCE 及列默认值）。"
        ) from e
    audit_seq = int(row[0])

    log_workflow_audit_appended(
        event_id=nid,
        video_id=video_id,
        actor_id=actor_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        audit_sequence=audit_seq,
        detail=detail,
    )


def _append_event_application_sequence(
    db: Session,
    *,
    video_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    from_status: str,
    to_status: str,
    detail: dict[str, Any] | None,
) -> None:
    """SQLite 等：MAX+1 + 撞唯一时 SAVEPOINT 重试。"""
    last: IntegrityError | None = None
    for attempt in range(1, _APPEND_EVENT_MAX_ATTEMPTS + 1):
        ev: VideoWorkflowEvent | None = None
        try:
            with db.begin_nested():
                ev = VideoWorkflowEvent(
                    video_id=video_id,
                    actor_id=actor_id,
                    action=action,
                    from_status=from_status,
                    to_status=to_status,
                    detail=detail,
                    audit_sequence=_next_global_audit_sequence(db),
                )
                db.add(ev)
                db.flush()
            assert ev is not None
            log_workflow_audit_appended(
                event_id=ev.id,
                video_id=video_id,
                actor_id=actor_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                audit_sequence=ev.audit_sequence,
                detail=detail,
            )
            return
        except IntegrityError as e:
            last = e
            if not _is_audit_sequence_unique_violation(e):
                raise
            if ev is not None:
                db.expunge(ev)
            log_workflow_audit_sequence_retry(video_id=video_id, action=action, attempt=attempt)
    log_workflow_audit_sequence_exhausted(
        video_id=video_id,
        action=action,
        attempts=_APPEND_EVENT_MAX_ATTEMPTS,
    )
    raise RuntimeError("分配 audit_sequence 重试次数耗尽") from last


