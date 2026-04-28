from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.comment import Comment


def max_updated_at_active_for_video(db: Session, *, video_id: uuid.UUID) -> datetime | None:
    """未软删评论中 ``updated_at`` 的最大值（无行时为 ``None``）。"""
    return db.scalar(
        select(func.max(Comment.updated_at)).where(
            Comment.video_id == video_id,
            Comment.is_deleted.is_(False),
        )
    )


def count_active_for_video(db: Session, *, video_id: uuid.UUID) -> int:
    """未软删评论总数（与分页 ``limit/offset`` 独立）。"""
    return int(
        db.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.video_id == video_id, Comment.is_deleted.is_(False))
        )
        or 0
    )


def create(
    db: Session,
    *,
    video_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> Comment:
    now = datetime.now(timezone.utc)
    c = Comment(
        video_id=video_id,
        user_id=user_id,
        content=content,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    db.flush()
    return c


def get_by_id(db: Session, comment_id: uuid.UUID) -> Comment | None:
    return db.get(Comment, comment_id)


def list_for_video(
    db: Session,
    *,
    video_id: uuid.UUID,
    limit: int,
    offset: int = 0,
    include_deleted: bool = False,
    after_comment_id: uuid.UUID | None = None,
) -> tuple[list[Comment], bool]:
    """按 ``(created_at, id)`` 升序；返回 ``(rows, has_more)``（多拉一行判尾页）。

    热路径索引见迁移 ``0016_comments_partial_list_index``。
    """
    stmt = select(Comment).where(Comment.video_id == video_id)
    if not include_deleted:
        stmt = stmt.where(Comment.is_deleted.is_(False))
    if after_comment_id is not None:
        anchor = db.get(Comment, after_comment_id)
        if anchor is None or anchor.video_id != video_id:
            return [], False
        if anchor.is_deleted and not include_deleted:
            return [], False
        stmt = stmt.where(
            or_(
                Comment.created_at > anchor.created_at,
                and_(Comment.created_at == anchor.created_at, Comment.id > anchor.id),
            )
        )
        stmt = stmt.order_by(Comment.created_at.asc(), Comment.id.asc()).limit(limit + 1)
    else:
        stmt = (
            stmt.order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
    raw = list(db.scalars(stmt).all())
    has_more = len(raw) > limit
    return raw[:limit], has_more


def soft_delete(db: Session, comment: Comment) -> None:
    comment.is_deleted = True
    comment.updated_at = datetime.now(timezone.utc)
    db.add(comment)
    db.flush()
