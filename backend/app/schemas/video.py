from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.video_workflow_rules import WorkflowPostKind
from app.models.enums import VideoStatus, VodTranscodeStatus, VodUploadStatus
from app.schemas.vod_inputs import (
    MAX_VIDEO_DURATION_SECONDS,
    reject_path_like_source_name,
    validate_vod_video_id_shape,
)


class TagBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class VideoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512, description="服务端按 MAX_VIDEO_TITLE_LENGTH 收紧校验")
    description: str | None = Field(default=None, max_length=200_000)
    cover_url: str | None = Field(default=None, max_length=2048)
    video_url: str | None = Field(default=None, max_length=2048)
    category_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=64)
    vod_video_id: str | None = Field(
        default=None,
        max_length=128,
        description="仅管理员可在创建时写入；普通用户须使用 PATCH …/bind-vod",
    )
    duration_seconds: int | None = Field(default=None, ge=0, le=MAX_VIDEO_DURATION_SECONDS)
    source_file_name: str | None = Field(default=None, max_length=512)

    @field_validator("title", "description", "cover_url", "video_url", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("vod_video_id", "source_file_name", mode="before")
    @classmethod
    def strip_optional_vod_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("vod_video_id", mode="after")
    @classmethod
    def vod_video_id_shape_create(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_vod_video_id_shape(v)

    @field_validator("source_file_name", mode="after")
    @classmethod
    def source_file_name_safe_create(cls, v: str | None) -> str | None:
        return reject_path_like_source_name(v)


class VideoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=200_000)
    cover_url: str | None = Field(default=None, max_length=2048)
    video_url: str | None = Field(default=None, max_length=2048)
    category_id: uuid.UUID | None = None
    status: VideoStatus | None = None
    tag_ids: list[uuid.UUID] | None = Field(default=None, max_length=64)
    upload_status: VodUploadStatus | None = None
    transcode_status: VodTranscodeStatus | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=MAX_VIDEO_DURATION_SECONDS)
    source_file_name: str | None = Field(default=None, max_length=512)

    @field_validator("title", "description", "cover_url", "video_url", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("source_file_name", mode="before")
    @classmethod
    def strip_source_file_name(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("source_file_name", mode="after")
    @classmethod
    def source_file_name_safe_update(cls, v: str | None) -> str | None:
        return reject_path_like_source_name(v)


class VideoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = Field(
        default=None,
        description="简介；列表与详情一致，仅对已授权可见的稿件返回（与 ``GET /videos/{id}`` 规则相同）。",
    )
    cover_url: str | None
    status: VideoStatus
    author_id: uuid.UUID
    author_username: str | None = None
    category_id: uuid.UUID | None
    views_count: int
    likes_count: int
    favorites_count: int
    comments_count: int = Field(default=0, ge=0)
    published_at: datetime | None
    rejection_reason: str | None = None
    vod_video_id: str | None = Field(
        default=None,
        description="阿里云 VOD VideoId；列表/详情仅作者或管理员可见，其它身份为 null。",
    )
    upload_status: VodUploadStatus
    transcode_status: VodTranscodeStatus
    duration_seconds: int | None = None
    source_file_name: str | None = Field(
        default=None,
        description="来源文件名（basename）；仅作者或管理员可见，其它身份为 null。",
    )
    created_at: datetime
    tags: list[TagBrief] = Field(default_factory=list)
    recommendation_reason: dict[str, int] | None = None
    recommendation_text: str | None = None


class VideoFeedResponse(BaseModel):
    items: list[VideoListItem]
    total: int = Field(ge=0)
    hasMore: bool
    nextCursor: str | None = None
    algorithmMode: str = "personalized"
    personalized: bool = True
    explanation: str | None = None


class VideoWorkflowEventOut(BaseModel):
    """工作流审计条目（管理员或作者只读列表）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    from_status: str
    to_status: str
    detail: dict[str, Any] | None = None
    created_at: datetime

    @field_validator("action", mode="after")
    @classmethod
    def action_is_known_workflow_kind(cls, v: str) -> str:
        allowed = frozenset(x.value for x in WorkflowPostKind)
        if v not in allowed:
            raise ValueError(f"未知的工作流 action: {v!r}")
        return v

    @field_validator("from_status", "to_status", mode="after")
    @classmethod
    def status_strings_are_video_status(cls, v: str) -> str:
        try:
            VideoStatus(v)
        except ValueError as e:
            raise ValueError(f"非法视频状态: {v!r}") from e
        return v


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    cover_url: str | None
    video_url: str | None
    status: VideoStatus
    author_id: uuid.UUID
    category_id: uuid.UUID | None
    views_count: int
    likes_count: int
    favorites_count: int
    published_at: datetime | None
    rejection_reason: str | None = None
    vod_video_id: str | None = Field(
        default=None,
        description="阿里云 VOD VideoId；仅作者或管理员在详情中可见，其它身份为 null。",
    )
    upload_status: VodUploadStatus
    transcode_status: VodTranscodeStatus
    duration_seconds: int | None = None
    source_file_name: str | None = Field(
        default=None,
        description="来源文件名；仅作者或管理员可见，其它身份为 null。",
    )
    created_at: datetime
    updated_at: datetime
    row_version: int
    tags: list[TagBrief] = Field(default_factory=list)


class VideoBindVodRequest(BaseModel):
    """将本地稿件与阿里云 VOD ``VideoId`` 绑定；可带 ``Idempotency-Key`` 与 PATCH 视频一致。"""

    model_config = ConfigDict(extra="forbid")

    vod_video_id: str = Field(min_length=1, max_length=128)
    upload_status: VodUploadStatus | None = Field(
        default=None,
        description="省略时默认 pending（已拿到媒资 ID、等待上传/回调推进）",
    )
    transcode_status: VodTranscodeStatus | None = Field(default=None, description="省略时默认 pending")
    duration_seconds: int | None = Field(default=None, ge=0, le=MAX_VIDEO_DURATION_SECONDS)
    source_file_name: str | None = Field(default=None, max_length=512)

    @field_validator("vod_video_id", "source_file_name", mode="before")
    @classmethod
    def strip_bind_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v

    @field_validator("vod_video_id", mode="after")
    @classmethod
    def vod_video_id_shape_bind(cls, v: str) -> str:
        return validate_vod_video_id_shape(v)

    @field_validator("source_file_name", mode="after")
    @classmethod
    def source_file_name_safe_bind(cls, v: str | None) -> str | None:
        return reject_path_like_source_name(v)


class VideoRejectRequest(BaseModel):
    """管理员驳回时必填驳回原因（落库便于作者整改与审计）。"""

    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(min_length=1, max_length=2000)

    @field_validator("rejection_reason", mode="before")
    @classmethod
    def strip_reason(cls, v):
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v
