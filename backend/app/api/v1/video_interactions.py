"""视频点赞与收藏（阶段 9.2）：挂载在 ``/videos/{video_id}`` 下。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import CurrentUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.schemas.video_interaction import VideoInteractionCountsOut, VideoMyInteractionsOut
from app.services import video_interaction_service

router = APIRouter()


@router.get(
    "/{video_id}/my-interactions",
    response_model=VideoMyInteractionsOut,
    summary="当前用户在该视频的互动状态",
    description="须登录；能查看该视频即可查询（含非发布态作者/管理员场景）。",
)
def get_my_video_interactions(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoMyInteractionsOut:
    return video_interaction_service.get_my_interaction_flags(db, current_user, video_id)


@router.post(
    "/{video_id}/like",
    response_model=VideoInteractionCountsOut,
    summary="点赞视频",
    description="须登录；仅 ``published`` 视频；同一用户对同一视频仅可点赞一次。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def post_video_like(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoInteractionCountsOut:
    vid, lc, fc = video_interaction_service.like_video(db, current_user, video_id)
    return VideoInteractionCountsOut(video_id=vid, likes_count=lc, favorites_count=fc)


@router.delete(
    "/{video_id}/like",
    response_model=VideoInteractionCountsOut,
    summary="取消点赞",
    description="须登录；若未点赞则 404。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def delete_video_like(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoInteractionCountsOut:
    vid, lc, fc = video_interaction_service.unlike_video(db, current_user, video_id)
    return VideoInteractionCountsOut(video_id=vid, likes_count=lc, favorites_count=fc)


@router.post(
    "/{video_id}/favorite",
    response_model=VideoInteractionCountsOut,
    summary="收藏视频",
    description="须登录；仅 ``published`` 视频；同一用户对同一视频仅可收藏一次。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def post_video_favorite(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoInteractionCountsOut:
    vid, lc, fc = video_interaction_service.favorite_video(db, current_user, video_id)
    return VideoInteractionCountsOut(video_id=vid, likes_count=lc, favorites_count=fc)


@router.delete(
    "/{video_id}/favorite",
    response_model=VideoInteractionCountsOut,
    summary="取消收藏",
    description="须登录；若未收藏则 404。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def delete_video_favorite(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoInteractionCountsOut:
    vid, lc, fc = video_interaction_service.unfavorite_video(db, current_user, video_id)
    return VideoInteractionCountsOut(video_id=vid, likes_count=lc, favorites_count=fc)
