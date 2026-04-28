"""评论业务规则：与视频可见性、发布态、软删除权限对齐。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.comment_action_log import log_comment_created, log_comment_soft_deleted
from app.core.comment_codes import (
    COMMENT_FORBIDDEN,
    COMMENT_NOT_FOUND,
    COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE,
    COMMENT_RATE_LIMITED,
    COMMENT_VIDEO_NOT_PUBLISHED,
)
from app.core.comment_rate_limit import CommentRateLimitBackendError, consume_comment_post_slot
from app.core.config import settings
from app.infrastructure.observability.comment_metrics import (
    inc_comment_created,
    inc_comment_rate_limited,
    inc_comment_soft_deleted,
)
from app.core.exceptions import AppError
from app.core.video_codes import VIDEO_NOT_FOUND
from app.models.comment import Comment
from app.models.enums import UserRole, VideoStatus
from app.models.user import User
from app.repositories import comment_repository, video_repository
from app.services import notification_service
from app.services.video_service import can_view_video

logger = logging.getLogger(__name__)


def create_comment(db: Session, actor: User, video_id: uuid.UUID, content: str) -> Comment:
    """登录用户发表评论；仅 ``published`` 视频可发（含作者本人）。"""
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, actor):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if v.status != VideoStatus.PUBLISHED:
        raise AppError("仅已发布视频可发表评论", status_code=400, code=COMMENT_VIDEO_NOT_PUBLISHED)
    bucket = f"{actor.id}:{video_id}"
    cap = settings.COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE
    try:
        ok, ra = consume_comment_post_slot(bucket, max_per_minute=cap)
    except CommentRateLimitBackendError as e:
        logger.error(
            "comment rate limit redis failed (strict mode, no memory fallback): %s",
            e,
            exc_info=True,
        )
        raise AppError(
            "评论限流服务暂不可用，请稍后重试",
            status_code=503,
            code=COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE,
        ) from e
    if not ok:
        inc_comment_rate_limited()
        hdr = {"Retry-After": str(ra)} if ra is not None else {}
        raise AppError(
            "发表评论过于频繁，请稍后再试",
            status_code=429,
            code=COMMENT_RATE_LIMITED,
            headers=hdr,
        )
    c = comment_repository.create(db, video_id=video_id, user_id=actor.id, content=content)
    if v.author_id != actor.id:
        notification_service.create_event(
            db,
            user_id=v.author_id,
            title=f"{actor.username} 评论了你的视频",
            body=content[:120],
            kind="comment",
            action_url=f"/videos/{video_id}",
        )
    db.commit()
    out = comment_repository.get_by_id(db, c.id)
    assert out is not None
    log_comment_created(
        comment_id=out.id,
        video_id=video_id,
        user_id=actor.id,
        content_len=len(out.content),
    )
    inc_comment_created()
    return out


def peek_comment_list_aggregate(
    db: Session,
    viewer: User | None,
    video_id: uuid.UUID,
) -> tuple[int, datetime | None]:
    """校验列表可见性后，仅返回未软删总数与 ``max(updated_at)``（供 ETag，不拉列表行）。"""
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    total = comment_repository.count_active_for_video(db, video_id=video_id)
    max_u = comment_repository.max_updated_at_active_for_video(db, video_id=video_id)
    return total, max_u


def list_comments(
    db: Session,
    viewer: User | None,
    video_id: uuid.UUID,
    *,
    limit: int,
    offset: int = 0,
    after_comment_id: uuid.UUID | None = None,
) -> tuple[list[Comment], int, bool]:
    """列出未软删除评论及未软删总数、是否还有下一页；视频可见性与 ``GET /videos/{id}`` 一致。"""
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    total = comment_repository.count_active_for_video(db, video_id=video_id)
    rows, has_more = comment_repository.list_for_video(
        db,
        video_id=video_id,
        limit=limit,
        offset=offset,
        after_comment_id=after_comment_id,
    )
    return rows, total, has_more


def delete_comment(db: Session, actor: User, comment_id: uuid.UUID) -> None:
    """评论作者或管理员软删除。"""
    c = comment_repository.get_by_id(db, comment_id)
    if c is None or c.is_deleted:
        raise AppError("评论不存在", status_code=404, code=COMMENT_NOT_FOUND)
    if actor.role != UserRole.ADMIN and c.user_id != actor.id:
        raise AppError("无权删除该评论", status_code=403, code=COMMENT_FORBIDDEN)
    v = video_repository.get_by_id(db, c.video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, actor):
        raise AppError("无权删除该评论", status_code=403, code=COMMENT_FORBIDDEN)
    comment_repository.soft_delete(db, c)
    db.commit()
    log_comment_soft_deleted(comment_id=comment_id, video_id=c.video_id, actor_id=actor.id)
    inc_comment_soft_deleted()
