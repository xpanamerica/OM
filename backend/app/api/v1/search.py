"""阶段 13：数据库级视频搜索（无 Elasticsearch）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import DbSession
from app.api.dependencies.auth import OptionalUser
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL
from app.api.v1.video_query import VideoListLimit, VideoListOffset
from app.core.client_ip import resolved_client_ip
from app.core.config import settings
from app.core.search_rate_limit import consume_search_slot_or_raise
from app.schemas.video import VideoListItem
from app.services import video_privacy, video_service

router = APIRouter()


@router.get(
    "/videos",
    response_model=list[VideoListItem],
    summary="搜索视频",
    description=(
        "数据库级搜索：``keyword`` 匹配 **title** 与 **description**（ILIKE）；"
        "可选 ``category_id`` / ``tag_id``；``sort_by`` 支持 latest / views / likes。"
        "**非管理员**仅返回 ``published``；**管理员**（须登录）可命中全部状态。"
        "响应头 ``X-Total-Count`` 为命中总数；``offset``+``limit`` 分页。"
        "关键词长度上限见环境变量 ``VIDEO_SEARCH_KEYWORD_MAX_LENGTH``（超长 400）。"
        "``VIDEO_SEARCH_MAX_REQUESTS_PER_MINUTE``>0 时按 IP 滑动窗口限流（429 + ``Retry-After``）。"
    ),
    responses={
        400: {"description": "sort_by 非法、分类/标签不存在、或关键词超长（`VIDEO_SEARCH_KEYWORD_TOO_LONG`）"},
        429: {"description": "超过 ``VIDEO_SEARCH_MAX_REQUESTS_PER_MINUTE``（`VIDEO_SEARCH_RATE_LIMITED`）"},
    },
)
def search_videos(
    request: Request,
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    keyword: str | None = Query(
        default=None,
        max_length=512,
        description=(
            "在标题与描述中模糊匹配（不区分大小写）；省略则不按关键词过滤。"
            f"业务层按 ``VIDEO_SEARCH_KEYWORD_MAX_LENGTH``（当前默认 {settings.VIDEO_SEARCH_KEYWORD_MAX_LENGTH}）校验长度。"
        ),
    ),
    category_id: uuid.UUID | None = Query(default=None, description="按分类筛选"),
    tag_id: uuid.UUID | None = Query(default=None, description="按单个标签筛选"),
    sort_by: str = Query(
        default="latest",
        description="排序：`latest` 创建时间倒序；`views` 播放量；`likes` 点赞数",
        pattern="^(latest|views|likes)$",
    ),
    offset: VideoListOffset = 0,
    limit: VideoListLimit = 20,
):
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    consume_search_slot_or_raise(ip)

    items, total = video_service.search_videos(
        db,
        optional_user,
        keyword=keyword,
        category_id=category_id,
        tag_id=tag_id,
        sort_by=sort_by,
        offset=offset,
        limit=limit,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return [video_privacy.video_list_item_for_viewer(v, optional_user, db) for v in items]
