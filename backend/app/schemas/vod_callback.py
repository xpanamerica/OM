"""阿里云 VOD HTTP 回调体（兼容官方字段名，额外字段透传便于扩展）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VodCallbackIn(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    event_type: str | None = Field(default=None, alias="EventType")
    video_id: str | None = Field(default=None, alias="VideoId")
    status: str | None = Field(default=None, alias="Status")
    stream_infos: list[dict[str, Any]] | None = Field(default=None, alias="StreamInfos")


class VodCallbackAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = Field(description="已鉴权并解析请求（含未知事件也会 accepted）")
    updated: bool = Field(description="是否更新了本地 videos 行")
    video_id: str | None = Field(default=None, description="本站视频 UUID，未匹配到则为 null")
    vod_video_id: str | None = Field(default=None, description="回调中的 VideoId")
    event_kind: str = Field(description="内部归一化事件类别，便于观测")
