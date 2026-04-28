from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.user_notification import UserNotification
from app.repositories import notification_repository


_WELCOME_KIND = "welcome"


def _ensure_welcome_notification(db: Session, *, user_id: uuid.UUID) -> None:
    """首次打开消息列表时插入一条欢迎通知（幂等：按 kind 判断）。"""
    total = notification_repository.count_for_user(db, user_id=user_id)
    if total > 0:
        return
    notification_repository.add(
        db,
        UserNotification(
            user_id=user_id,
            title="欢迎使用恒频OM",
            body="你可以在「个人中心」查看播放记录、收藏与互动消息；点赞、评论与系统提醒会出现在此处。",
            kind=_WELCOME_KIND,
            action_url=None,
        ),
    )
    db.commit()


def list_my_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[UserNotification], int, int]:
    _ensure_welcome_notification(db, user_id=user_id)
    items, total = notification_repository.list_for_user(db, user_id=user_id, offset=offset, limit=limit)
    unread = notification_repository.count_unread(db, user_id=user_id)
    return items, total, unread


def mark_read(db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID) -> UserNotification | None:
    from datetime import UTC, datetime

    row = notification_repository.get_for_user(db, user_id=user_id, notification_id=notification_id)
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = datetime.now(tz=UTC)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def mark_all_read(db: Session, *, user_id: uuid.UUID) -> int:
    from datetime import UTC, datetime

    now = datetime.now(tz=UTC)
    stmt = (
        update(UserNotification)
        .where(UserNotification.user_id == user_id, UserNotification.read_at.is_(None))
        .values(read_at=now)
    )
    res = db.execute(stmt)
    db.commit()
    return int(res.rowcount or 0)


def unread_count_for_hub(db: Session, *, user_id: uuid.UUID) -> int:
    """个人中心角标：与列表一致，必要时插入欢迎通知后再计数。"""
    _ensure_welcome_notification(db, user_id=user_id)
    return notification_repository.count_unread(db, user_id=user_id)


def create_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str | None,
    kind: str,
    action_url: str | None = None,
) -> UserNotification:
    """写入一条业务事件通知；调用方负责最终 commit。"""
    return notification_repository.add(
        db,
        UserNotification(
            user_id=user_id,
            title=title,
            body=body,
            kind=kind[:32],
            action_url=action_url,
        ),
    )
