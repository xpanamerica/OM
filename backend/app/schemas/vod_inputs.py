"""VOD 绑定相关输入校验（视频 Schema 与绑定请求复用）。"""

from __future__ import annotations

# 合理上限：超长数值多为脏数据或整数溢出风险（7 天 × 秒）
MAX_VIDEO_DURATION_SECONDS = 604_800


def reject_path_like_source_name(v: str | None) -> str | None:
    """``source_file_name`` 仅允许 basename，禁止路径穿越与分隔符。"""
    if v is None:
        return None
    if ".." in v or "/" in v or "\\" in v or "\x00" in v:
        raise ValueError("source_file_name 不得包含路径、反斜杠或 ..")
    return v


def validate_vod_video_id_shape(v: str) -> str:
    """CreateUploadVideo 返回的 VideoId：无空白、无控制字符。"""
    if any(c.isspace() for c in v):
        raise ValueError("vod_video_id 不得包含空白字符")
    if any(ord(c) < 32 for c in v):
        raise ValueError("vod_video_id 含非法控制字符")
    return v
