"""视频 JSON 中的 VOD 绑定细节：仅作者与管理员可见（最终对外暴露把关）。"""

from __future__ import annotations

from app.models.enums import UserRole
from app.models.user import User
from app.models.video import Video
from app.repositories import comment_repository, user_repository
from app.schemas.video import VideoListItem, VideoResponse
from sqlalchemy.orm import Session


def viewer_may_see_vod_binding_details(video: Video, viewer: User | None) -> bool:
    """``vod_video_id`` / ``source_file_name`` 等绑定细节是否可对当前查看者展示。"""
    if viewer is None:
        return False
    if viewer.role == UserRole.ADMIN:
        return True
    return video.author_id == viewer.id


def video_response_for_viewer(video: Video, viewer: User | None) -> VideoResponse:
    base = VideoResponse.model_validate(video)
    if viewer_may_see_vod_binding_details(video, viewer):
        return base
    return base.model_copy(update={"vod_video_id": None, "source_file_name": None})


def video_list_item_for_viewer(video: Video, viewer: User | None, db: Session | None = None) -> VideoListItem:
    base = VideoListItem.model_validate(video)
    extra: dict[str, object] = {}
    if db is not None:
        author = user_repository.get_by_id(db, video.author_id)
        extra["author_username"] = author.username if author is not None else None
        extra["comments_count"] = comment_repository.count_active_for_video(db, video_id=video.id)
    if viewer_may_see_vod_binding_details(video, viewer):
        return base.model_copy(update=extra) if extra else base
    return base.model_copy(update={"vod_video_id": None, "source_file_name": None, **extra})


def vod_detail_etag_tier(video: Video, viewer: User | None) -> str:
    """供 ETag 区分「脱敏 JSON」与「完整 JSON」，避免 304 与正文不一致。"""
    return "full" if viewer_may_see_vod_binding_details(video, viewer) else "redacted"
