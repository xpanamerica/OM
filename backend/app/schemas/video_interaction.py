from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class VideoMyInteractionsOut(BaseModel):
    """当前登录用户对该视频的点赞 / 收藏状态（只读）。"""

    model_config = ConfigDict(extra="forbid")

    liked: bool = Field(description="是否已点赞")
    favorited: bool = Field(description="是否已收藏")


class VideoInteractionCountsOut(BaseModel):
    """点赞/收藏写操作后的视频计数快照。"""

    model_config = ConfigDict(extra="forbid")

    video_id: uuid.UUID
    likes_count: int = Field(ge=0, description="``videos.likes_count``（应用层与 ``video_likes`` 行同事务维护）")
    favorites_count: int = Field(ge=0, description="``videos.favorites_count``")
