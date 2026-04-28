"""视频点赞与收藏：仅 ``published`` 可新增；计数与关联行同事务更新。"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.video_codes import VIDEO_NOT_FOUND
from app.core.video_interaction_codes import (
    VIDEO_FAVORITE_ALREADY_EXISTS,
    VIDEO_FAVORITE_NOT_FOUND,
    VIDEO_INTERACTION_REQUIRES_PUBLISHED,
    VIDEO_LIKE_ALREADY_EXISTS,
    VIDEO_LIKE_NOT_FOUND,
)
from app.models.enums import VideoStatus
from app.models.user import User
from app.models.video import Video
from app.repositories import (
    video_favorite_repository,
    video_like_repository,
    video_repository,
)
from app.services import notification_service, video_statistics_service
from app.services import video_privacy
from app.schemas.video import VideoListItem
from app.schemas.video_interaction import VideoMyInteractionsOut


def _require_published_interaction_target(v: Video) -> None:
    if v.status != VideoStatus.PUBLISHED:
        raise AppError(
            "仅已发布视频可点赞或收藏",
            status_code=400,
            code=VIDEO_INTERACTION_REQUIRES_PUBLISHED,
        )


def _load_video_or_404(db: Session, video_id: uuid.UUID, viewer: User) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    from app.services.video_service import can_view_video

    if not can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    return v


def _counts_out(db: Session, video_id: uuid.UUID) -> tuple[int, int]:
    v2 = video_repository.get_by_id(db, video_id, load_tags=False)
    assert v2 is not None
    return int(v2.likes_count), int(v2.favorites_count)


def _notify_author_for_interaction(
    db: Session,
    *,
    video: Video,
    actor: User,
    kind: str,
    title: str,
    body: str,
) -> None:
    if video.author_id == actor.id:
        return
    notification_service.create_event(
        db,
        user_id=video.author_id,
        title=title,
        body=body,
        kind=kind,
        action_url=f"/videos/{video.id}",
    )


def like_video(db: Session, actor: User, video_id: uuid.UUID) -> tuple[uuid.UUID, int, int]:
    v = _load_video_or_404(db, video_id, actor)
    _require_published_interaction_target(v)
    if video_like_repository.exists(db, user_id=actor.id, video_id=video_id):
        raise AppError("已经点赞过该视频", status_code=409, code=VIDEO_LIKE_ALREADY_EXISTS)
    try:
        video_like_repository.create(db, user_id=actor.id, video_id=video_id)
        video_statistics_service.adjust_likes_count(db, video_id=video_id, delta=1)
        _notify_author_for_interaction(
            db,
            video=v,
            actor=actor,
            kind="like",
            title=f"{actor.username} 赞了你的视频",
            body=v.title,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("已经点赞过该视频", status_code=409, code=VIDEO_LIKE_ALREADY_EXISTS) from None
    lc, fc = _counts_out(db, video_id)
    return video_id, lc, fc


def unlike_video(db: Session, actor: User, video_id: uuid.UUID) -> tuple[uuid.UUID, int, int]:
    """取消点赞：须能查看该视频；不要求当前仍为 ``published``。"""
    _load_video_or_404(db, video_id, actor)
    if not video_like_repository.delete_if_exists(db, user_id=actor.id, video_id=video_id):
        raise AppError("尚未点赞该视频", status_code=404, code=VIDEO_LIKE_NOT_FOUND)
    video_statistics_service.adjust_likes_count(db, video_id=video_id, delta=-1)
    db.commit()
    lc, fc = _counts_out(db, video_id)
    return video_id, lc, fc


def favorite_video(db: Session, actor: User, video_id: uuid.UUID) -> tuple[uuid.UUID, int, int]:
    v = _load_video_or_404(db, video_id, actor)
    _require_published_interaction_target(v)
    if video_favorite_repository.exists(db, user_id=actor.id, video_id=video_id):
        raise AppError("已经收藏过该视频", status_code=409, code=VIDEO_FAVORITE_ALREADY_EXISTS)
    try:
        video_favorite_repository.create(db, user_id=actor.id, video_id=video_id)
        video_statistics_service.adjust_favorites_count(db, video_id=video_id, delta=1)
        _notify_author_for_interaction(
            db,
            video=v,
            actor=actor,
            kind="favorite",
            title=f"{actor.username} 收藏了你的视频",
            body=v.title,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("已经收藏过该视频", status_code=409, code=VIDEO_FAVORITE_ALREADY_EXISTS) from None
    lc, fc = _counts_out(db, video_id)
    return video_id, lc, fc


def get_my_interaction_flags(db: Session, actor: User, video_id: uuid.UUID) -> VideoMyInteractionsOut:
    """当前用户在该视频上的点赞 / 收藏状态（能查看该视频即可查询）。"""
    _load_video_or_404(db, video_id, actor)
    liked = video_like_repository.exists(db, user_id=actor.id, video_id=video_id)
    favorited = video_favorite_repository.exists(db, user_id=actor.id, video_id=video_id)
    return VideoMyInteractionsOut(liked=liked, favorited=favorited)


def list_my_favorite_videos(
    db: Session, actor: User, *, offset: int, limit: int
) -> tuple[list[VideoListItem], int]:
    """当前用户已收藏且仍为 ``published`` 的视频列表（分页）。"""
    total = video_favorite_repository.count_published_favorites_by_user(db, user_id=actor.id)
    rows = video_favorite_repository.list_published_favorite_videos_by_user(
        db, user_id=actor.id, offset=offset, limit=limit
    )
    items = [video_privacy.video_list_item_for_viewer(v, actor, db) for v in rows]
    return items, total


def unfavorite_video(db: Session, actor: User, video_id: uuid.UUID) -> tuple[uuid.UUID, int, int]:
    """取消收藏：须能查看该视频。"""
    _load_video_or_404(db, video_id, actor)
    if not video_favorite_repository.delete_if_exists(db, user_id=actor.id, video_id=video_id):
        raise AppError("尚未收藏该视频", status_code=404, code=VIDEO_FAVORITE_NOT_FOUND)
    video_statistics_service.adjust_favorites_count(db, video_id=video_id, delta=-1)
    db.commit()
    lc, fc = _counts_out(db, video_id)
    return video_id, lc, fc
