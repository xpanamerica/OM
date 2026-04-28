"""阶段 11.3：播放交付（VOD PlayAuth 或本机磁盘 Range 流 URL）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VideoPlayResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "video_id": "550e8400-e29b-41d4-a716-446655440000",
                    "playback_mode": "vod",
                    "vod_video_id": "abc123",
                    "play_auth": "eyJ…",
                    "stream_url": None,
                    "expire_time": "2026-04-26T12:00:00Z",
                    "request_id": "rid",
                },
                {
                    "video_id": "550e8400-e29b-41d4-a716-446655440000",
                    "playback_mode": "local",
                    "vod_video_id": None,
                    "play_auth": None,
                    "stream_url": "https://api.example.com/api/v1/videos/550e8400-e29b-41d4-a716-446655440000/local-stream?token=…",
                    "expire_time": "2026-04-26T14:00:00Z",
                    "request_id": None,
                },
            ]
        }
    )

    video_id: uuid.UUID = Field(description="本站视频主键")
    playback_mode: Literal["vod", "local"] = Field(
        default="vod",
        description="``vod``：使用 ``play_auth`` + 阿里云播放器；``local``：使用 ``stream_url``（HTML5 video / 支持 Range）。",
    )
    vod_video_id: str | None = Field(default=None, description="阿里云 VOD VideoId；本机播放时为 null。")
    play_auth: str | None = Field(default=None, description="GetVideoPlayAuth 短时凭证；本机播放时为 null。")
    stream_url: str | None = Field(
        default=None,
        description="本机成片直链（含短时 query token）；浏览器 ``<video src>`` 使用，勿长期缓存。",
    )
    expire_time: datetime | None = Field(
        default=None,
        description="凭证或 stream token 预计失效时间（UTC）；实际以服务端校验为准。",
    )
    request_id: str | None = Field(default=None, description="阿里云 RequestId；本机播放时通常为 null。")
