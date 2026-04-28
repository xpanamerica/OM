"""阶段 11.1：阿里云 VOD 上传凭证请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.vod_inputs import validate_vod_video_id_shape


class VodCreateUploadRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=512,
        description="视频标题（将传给阿里云 CreateUploadVideo）；服务端另按 MAX_VIDEO_TITLE_LENGTH 校验。",
    )
    filename: str = Field(
        min_length=1,
        max_length=512,
        description="待上传文件名，须含扩展名（如 clip.mp4），禁止路径分隔符",
    )
    file_size: int = Field(
        ge=1,
        description="拟上传文件字节数；须不超过 MAX_VIDEO_SIZE_MB，并与扩展名白名单一并校验",
    )
    description: str | None = Field(default=None, max_length=200_000)
    cover_url: str | None = Field(default=None, max_length=2048, description="可选封面 URL")

    @field_validator("filename", mode="before")
    @classmethod
    def filename_not_pathlike(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        s = v.strip()
        if ".." in s or "/" in s or "\\" in s or "\x00" in s:
            raise ValueError("filename 不得包含路径或 ..")
        if "." not in s:
            raise ValueError("filename 须包含扩展名，例如 video.mp4")
        return s

    @field_validator("title", "description", "cover_url", mode="before")
    @classmethod
    def strip_optional_strings(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s or None
        return v


class VodCreateUploadResponse(BaseModel):
    video_id_from_vod: str = Field(description="阿里云返回的 VideoId")
    upload_address: str
    upload_auth: str
    request_id: str

    model_config = {"json_schema_extra": {"examples": [{"video_id_from_vod": "abc", "upload_address": "...", "upload_auth": "...", "request_id": "rid"}]}}


class VodRefreshUploadRequest(BaseModel):
    """刷新已创建媒资的上传地址与 STS（``RefreshUploadVideo``）；须为曾成功 ``CreateUploadVideo`` 的同一用户（管理员除外）。"""

    vod_video_id: str = Field(min_length=1, max_length=128, description="CreateUploadVideo 返回的 VideoId")

    @field_validator("vod_video_id", mode="before")
    @classmethod
    def strip_vid(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("vod_video_id", mode="after")
    @classmethod
    def shape_vid(cls, v: str) -> str:
        return validate_vod_video_id_shape(v)
