from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.video import VideoListItem


class ProfileHubOut(BaseModel):
    """个人中心聚合（关注 / 粉丝 / 获赞与收藏 / 最近稿件 / 未读互动消息数）。"""

    following_count: int = Field(ge=0)
    followers_count: int = Field(ge=0)
    friends_count: int = Field(ge=0)
    pending_friend_request_count: int = Field(ge=0)
    likes_and_favorites_received: int = Field(ge=0)
    avatar_url: str | None = None
    unread_notification_count: int = Field(ge=0)
    recent_videos: list[VideoListItem]
