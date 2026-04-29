from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminPlatformSettingsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_publish_without_review_enabled: bool = Field(
        description="开启后，用户提交视频时直接发布，不进入待审核队列。"
    )
    registration_invite_code_required: bool = Field(
        description="开启后，公开注册必须提交有效且未过期的邀请码；关闭后适用于正式上线开放注册。"
    )


class AdminPlatformSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_publish_without_review_enabled: bool | None = Field(
        default=None,
        description="开启后，用户提交视频时直接发布，不进入待审核队列。",
    )
    registration_invite_code_required: bool | None = Field(
        default=None,
        description="开启后须凭邀请码注册；关闭后开放注册（邀请码可选且不参与校验）。",
    )


class AdminPlatformStatsOut(BaseModel):
    """全站基础统计（管理员只读）。"""

    model_config = ConfigDict(extra="forbid")

    users_total: int = Field(ge=0, description="未删除用户总数")
    videos_total: int = Field(ge=0, description="视频总行数")
    videos_published: int = Field(ge=0, description="``published`` 状态视频数")
    videos_pending_review: int = Field(ge=0, description="``pending_review`` 状态视频数")
    total_views_count: int = Field(ge=0, description="``sum(videos.views_count)``")
    total_likes_count: int = Field(ge=0, description="``sum(videos.likes_count)``")
    total_favorites_count: int = Field(ge=0, description="``sum(videos.favorites_count)``")


class AdminUserActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool = Field(description="``true`` 启用，``false`` 禁用")


class AdminBulkDeleteUsersOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: int = Field(ge=0, description="本次软删除的用户数量")
