from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user import User
from app.repositories import (
    user_block_repository,
    user_follow_repository,
    user_friend_request_repository,
    user_repository,
    video_repository,
)
from app.schemas.profile_hub import ProfileHubOut
from app.services import notification_service, video_privacy


def build_profile_hub(db: Session, user: User) -> ProfileHubOut:
    following = user_follow_repository.count_following(db, user_id=user.id)
    followers = user_follow_repository.count_followers(db, user_id=user.id)
    friends = user_follow_repository.count_mutual_friends(db, user_id=user.id)
    pending_friend_requests = user_friend_request_repository.count_pending_incoming(db, recipient_id=user.id)
    likes_recv = video_repository.sum_published_likes_and_favorites_on_author_videos(db, author_id=user.id)
    unread = notification_service.unread_count_for_hub(db, user_id=user.id)
    raw = video_repository.list_author_owned_videos_for_profile(db, author_id=user.id, offset=0, limit=12)
    recent = [video_privacy.video_list_item_for_viewer(v, user, db) for v in raw]
    return ProfileHubOut(
        following_count=following,
        followers_count=followers,
        friends_count=friends,
        pending_friend_request_count=pending_friend_requests,
        likes_and_favorites_received=likes_recv,
        avatar_url=user.avatar_url,
        unread_notification_count=unread,
        recent_videos=recent,
    )


def follow_user(db: Session, actor: User, followee_id: uuid.UUID) -> None:
    if followee_id == actor.id:
        raise AppError("不能关注自己", status_code=400)
    if user_repository.get_by_id(db, followee_id) is None:
        raise AppError("用户不存在", status_code=404)
    if user_block_repository.any_between(db, user_a=actor.id, user_b=followee_id):
        raise AppError("无法关注该用户", status_code=403)
    if user_follow_repository.exists(db, follower_id=actor.id, followee_id=followee_id):
        raise AppError("已经关注", status_code=409)
    followee = user_repository.get_by_id(db, followee_id)
    user_follow_repository.create(db, follower_id=actor.id, followee_id=followee_id)
    if followee is not None:
        notification_service.create_event(
            db,
            user_id=followee_id,
            title=f"{actor.username} 关注了你",
            body="你可以进入对方主页查看资料，互相关注后可开启私信交流。",
            kind="follow",
            action_url=f"/users/{actor.id}",
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("已经关注", status_code=409) from None


def unfollow_user(db: Session, actor: User, followee_id: uuid.UUID) -> None:
    n = user_follow_repository.delete_pair(db, follower_id=actor.id, followee_id=followee_id)
    if n == 0:
        raise AppError("尚未关注该用户", status_code=404)
    db.commit()
