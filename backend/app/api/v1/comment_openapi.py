"""评论路由共用的 OpenAPI 片段。"""

from typing import Any

from app.api.v1.video_openapi import (
    FORBIDDEN_403,
    NOT_FOUND_VIDEO,
    UNAUTH_401,
    UNPROCESSABLE_422,
    _ETAG_HEADER,
    _VARY_AUTH_HEADER,
)

_CACHE_CONTROL_HEADER: dict[str, Any] = {
    "schema": {"type": "string"},
    "description": (
        "`private, max-age=0, must-revalidate`：列表随评论变更；"
        "与分类/标签/视频列表等可变 GET 语义一致。"
    ),
}

COMMENT_LIST_GET_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **NOT_FOUND_VIDEO,
    400: {
        "description": "`cursor` 与 `offset` 同时传入，或 `cursor` 无法解码。",
    },
    200: {
        "description": "成功；`X-Total-Count` 为当前视频下未软删评论总数（与 `limit` 无关）。",
        "headers": {
            "X-Total-Count": {
                "schema": {"type": "string"},
                "description": "未软删除的评论条数。",
            },
            "X-Next-Cursor": {
                "schema": {"type": "string"},
                "description": "存在下一页时返回；值为末条评论 id 的 opaque 编码，下一请求作为 `cursor` 查询参数（与 offset 互斥）。",
            },
            "Cache-Control": _CACHE_CONTROL_HEADER,
            "ETag": _ETAG_HEADER,
            "Vary": _VARY_AUTH_HEADER,
        },
    },
    304: {
        "description": "列表未变化：`If-None-Match` 与当前 `ETag` 一致，无响应体。",
        "headers": {
            "X-Total-Count": {
                "schema": {"type": "string"},
                "description": "未软删除的评论条数（与 200 一致）。",
            },
            "Cache-Control": _CACHE_CONTROL_HEADER,
            "ETag": _ETAG_HEADER,
            "Vary": _VARY_AUTH_HEADER,
        },
    },
}

COMMENT_POST_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **NOT_FOUND_VIDEO,
    **UNPROCESSABLE_422,
    429: {
        "description": (
            "同一用户对同一视频发表评论过于频繁（`COMMENT_RATE_LIMITED`）；受 `COMMENT_POST_MAX_PER_VIDEO_PER_MINUTE` 约束。"
            "可能携带 `Retry-After`（秒）：距滑动窗口内最早一条记录滚出的大致等待时间。"
        ),
        "headers": {
            "Retry-After": {
                "schema": {"type": "string"},
                "description": "建议等待秒数（服务端估算，与滑动 60 秒窗口一致）。",
            },
        },
    },
    400: {
        "description": "业务校验失败：如对非 `published` 视频发表评论（`COMMENT_VIDEO_NOT_PUBLISHED`）。",
    },
    503: {
        "description": (
            "评论发帖限流依赖 Redis 且 ``COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY=false`` 时，"
            "Redis 不可用或脚本执行失败（`COMMENT_RATE_LIMIT_BACKEND_UNAVAILABLE`）。"
        ),
    },
    200: {
        "description": "成功",
        "headers": {
            "Cache-Control": {
                "schema": {"type": "string"},
                "description": "`private, no-store`：禁止缓存写操作响应。",
            },
        },
    },
}

COMMENT_DELETE_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    404: {"description": "评论不存在或已软删除。"},
    204: {
        "description": "软删除成功，无响应体。",
        "headers": {
            "Cache-Control": {
                "schema": {"type": "string"},
                "description": "`private, no-store`。",
            },
        },
    },
}
