"""播放记录（阶段 9.3）：仅 ``published`` 可上报；首条创建时 ``views_count + 1``。"""

from __future__ import annotations

import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.video_codes import VIDEO_NOT_FOUND
from app.core.video_cursor import decode_view_record_list_cursor, encode_view_record_list_cursor
from app.core.view_record_codes import (
    VIEW_RECORD_CONFLICT,
    VIEW_RECORD_CURSOR_INVALID,
    VIEW_RECORD_CURSOR_WITH_OFFSET,
    VIEW_RECORD_LAST_VIEWED_IN_FUTURE,
    VIEW_RECORD_REQUIRES_PUBLISHED,
)
from app.models.enums import VideoStatus
from app.models.user import User
from app.models.video import Video
from app.models.view_record import ViewRecord
from app.infrastructure.observability.view_record_metrics import (
    inc_view_record_contended_insert_merge,
    inc_view_record_upsert,
)
from app.repositories import video_repository, view_record_repository
from app.services import video_statistics_service
from app.schemas.view_record import ViewRecordOut, ViewRecordUpsertIn
from app.services.video_service import can_view_video

_VIEW_RECORD_POST_CONTENTION_ATTEMPTS = 16
_VIEW_RECORD_POST_CONTENTION_DELAY_S = 0.002


def _is_view_record_user_video_unique_violation(exc: IntegrityError) -> bool:
    """识别 ``(user_id, video_id)`` 唯一冲突：PostgreSQL ``23505`` + SQLite ``UNIQUE``。"""
    orig = getattr(exc, "orig", exc)
    if getattr(orig, "pgcode", None) == "23505":
        return True
    if isinstance(orig, sqlite3.IntegrityError):
        msg = str(orig).lower()
        return "unique" in msg and "view_records" in msg
    msg = str(orig).lower()
    if "uq_view_records_user_video" in msg:
        return True
    if "view_records" in msg and ("unique" in msg or "23505" in msg or "duplicate key" in msg):
        return True
    return False


def _get_view_record_after_unique_contention(
    db: Session, *, user_id: uuid.UUID, video_id: uuid.UUID
) -> ViewRecord | None:
    """并发首插：对方事务可能尚未提交，短暂重读避免误报 ``VIEW_RECORD_CONFLICT``。"""
    for _ in range(_VIEW_RECORD_POST_CONTENTION_ATTEMPTS):
        row = view_record_repository.get_by_user_and_video(db, user_id=user_id, video_id=video_id)
        if row is not None:
            return row
        time.sleep(_VIEW_RECORD_POST_CONTENTION_DELAY_S)
    return None


def _load_video_or_404(db: Session, video_id: uuid.UUID, viewer: User) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    return v


def _require_published_for_view_record(v: Video) -> None:
    if v.status != VideoStatus.PUBLISHED:
        raise AppError(
            "仅已发布视频可记录播放进度",
            status_code=400,
            code=VIEW_RECORD_REQUIRES_PUBLISHED,
        )


def _resolve_last_viewed_at(body: ViewRecordUpsertIn) -> datetime:
    if body.last_viewed_at is not None:
        return body.last_viewed_at
    return datetime.now(timezone.utc)


def _reject_future_last_viewed(ts: datetime, *, skew: timedelta = timedelta(minutes=5)) -> None:
    """拒绝明显未来的 ``last_viewed_at``（允许少量时钟偏差）。"""
    now = datetime.now(timezone.utc)
    if ts > now + skew:
        raise AppError(
            "last_viewed_at 不能晚于当前时间过多",
            status_code=400,
            code=VIEW_RECORD_LAST_VIEWED_IN_FUTURE,
        )


def upsert_view_record(db: Session, actor: User, video_id: uuid.UUID, body: ViewRecordUpsertIn) -> ViewRecordOut:
    v = _load_video_or_404(db, video_id, actor)
    _require_published_for_view_record(v)
    ts = _resolve_last_viewed_at(body)
    _reject_future_last_viewed(ts)
    existing = view_record_repository.get_by_user_and_video(db, user_id=actor.id, video_id=video_id)
    if existing is not None:
        view_record_repository.update_progress(
            db,
            existing,
            progress_seconds=body.progress_seconds,
            last_viewed_at=ts,
        )
        db.commit()
        row_out = view_record_repository.get_by_user_and_video(db, user_id=actor.id, video_id=video_id)
        assert row_out is not None
        inc_view_record_upsert()
        return ViewRecordOut.model_validate(row_out).model_copy(update={"video_title": v.title})

    try:
        view_record_repository.create(
            db,
            user_id=actor.id,
            video_id=video_id,
            progress_seconds=body.progress_seconds,
            last_viewed_at=ts,
        )
        video_statistics_service.increment_views_count(db, video_id=video_id)
        db.commit()
        row_out = view_record_repository.get_by_user_and_video(db, user_id=actor.id, video_id=video_id)
        assert row_out is not None
        inc_view_record_upsert()
        return ViewRecordOut.model_validate(row_out).model_copy(update={"video_title": v.title})
    except IntegrityError as e:
        db.rollback()
        if not _is_view_record_user_video_unique_violation(e):
            raise
        existing2 = _get_view_record_after_unique_contention(db, user_id=actor.id, video_id=video_id)
        if existing2 is None:
            raise AppError("播放记录冲突，请重试", status_code=409, code=VIEW_RECORD_CONFLICT) from None
        view_record_repository.update_progress(
            db,
            existing2,
            progress_seconds=body.progress_seconds,
            last_viewed_at=ts,
        )
        db.commit()
        row_out = view_record_repository.get_by_user_and_video(db, user_id=actor.id, video_id=video_id)
        assert row_out is not None
        inc_view_record_contended_insert_merge()
        inc_view_record_upsert()
        return ViewRecordOut.model_validate(row_out).model_copy(update={"video_title": v.title})


def list_my_view_records(
    db: Session,
    actor: User,
    *,
    offset: int,
    limit: int,
    cursor_token: str | None,
) -> tuple[list[ViewRecordOut], int, str | None, bool]:
    """返回 ``(items, total, next_cursor, has_more)``。"""
    cursor_before: tuple[datetime, uuid.UUID] | None = None
    if cursor_token and cursor_token.strip():
        if offset != 0:
            raise AppError(
                "使用 cursor 分页时请将 offset 设为 0",
                status_code=400,
                code=VIEW_RECORD_CURSOR_WITH_OFFSET,
            )
        try:
            cursor_before = decode_view_record_list_cursor(cursor_token.strip())
        except ValueError as e:
            raise AppError(str(e), status_code=400, code=VIEW_RECORD_CURSOR_INVALID) from None

    row_pairs, total = view_record_repository.list_by_user_page(
        db,
        user_id=actor.id,
        limit=limit,
        offset=offset,
        cursor_before=cursor_before,
    )
    outs = [
        ViewRecordOut.model_validate(rec).model_copy(update={"video_title": title})
        for rec, title in row_pairs
    ]

    if cursor_before is not None:
        has_more = len(row_pairs) == limit
    else:
        has_more = offset + len(row_pairs) < total

    next_cursor: str | None = None
    if has_more and row_pairs:
        last = row_pairs[-1][0]
        next_cursor = encode_view_record_list_cursor(last_viewed_at=last.last_viewed_at, row_id=last.id)

    return outs, total, next_cursor, has_more
