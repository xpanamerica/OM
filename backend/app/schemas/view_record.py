from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 模型无片长字段：用上限防止异常大整数；约 100 年秒级进度已远超业务需要
_VIEW_RECORD_PROGRESS_SECONDS_MAX = 86_400 * 366 * 100


class ViewRecordUpsertIn(BaseModel):
    """上报播放进度（创建或更新同一用户对同一视频的一行）。"""

    model_config = ConfigDict(extra="forbid")

    progress_seconds: int = Field(
        ge=0,
        le=_VIEW_RECORD_PROGRESS_SECONDS_MAX,
        description="已播放秒数（上限防滥用；片长校验待元数据字段后扩展）",
    )
    last_viewed_at: datetime | None = Field(
        default=None,
        description="客户端可选；缺省则由服务端使用当前 UTC 时间；含时区则归一为 UTC",
    )

    @field_validator("last_viewed_at")
    @classmethod
    def last_viewed_at_normalize_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ViewRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    user_id: uuid.UUID
    video_id: uuid.UUID
    progress_seconds: int = Field(ge=0)
    last_viewed_at: datetime
    created_at: datetime
    updated_at: datetime
    video_title: str | None = Field(
        default=None,
        description="关联视频标题；列表接口由 JOIN 填充，单条上报接口由当前视频填充",
    )

    @field_validator("last_viewed_at", "created_at", "updated_at", mode="before")
    @classmethod
    def datetime_coerce_utc(cls, v: object) -> object:
        """SQLite 等方言可能返回 naive；序列化前统一为 UTC aware。"""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return v
