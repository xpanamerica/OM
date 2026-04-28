"""视频路由共用的 OpenAPI 片段（中文说明、常见 HTTP 状态与响应头）。"""

from typing import Any

UNAUTH_401: dict[int, dict[str, Any]] = {
    401: {"description": "未携带令牌、令牌无效或已过期"},
}

FORBIDDEN_403: dict[int, dict[str, Any]] = {
    403: {"description": "无权执行该操作（如非作者修改他人视频、账号已停用）"},
}

NOT_FOUND_VIDEO: dict[int, dict[str, Any]] = {
    404: {"description": "视频不存在，或存在但当前身份不可见（与不存在统一为 404）"},
}

BAD_REQUEST_VIDEO: dict[int, dict[str, Any]] = {
    400: {
        "description": (
            "业务校验失败：如分类/标签不存在、非管理员使用 `status` 查询参数、"
            "审核边误用 PATCH（应改用 submit-review / approve / reject / offline 等 POST）、"
            "管理员对已发布视频误用 PATCH 下架（应改用 POST `/videos/{video_id}/offline`）等。"
        )
    },
}

UNPROCESSABLE_422: dict[int, dict[str, Any]] = {
    422: {"description": "请求体验证失败（如 `extra` 禁止字段、字段类型或长度不合法）"},
}

IDEMPOTENCY_CONFLICT: dict[int, dict[str, Any]] = {
    409: {
        "description": (
            "同一 `Idempotency-Key` 已与其它请求体绑定；"
            "请更换 Key 或保持与首次成功请求完全相同的 JSON 载荷。"
        )
    },
}

IDEMPOTENCY_BACKEND_UNAVAILABLE: dict[int, dict[str, Any]] = {
    503: {
        "description": (
            "已携带 `Idempotency-Key`，但当前配置禁止内存回退且 Redis 不可用；"
            "请稍后重试或修复 `REDIS_URL`。"
        )
    },
}

OPTIMISTIC_CONFLICT_409: dict[int, dict[str, Any]] = {
    409: {
        "description": (
            "并发更新冲突：他人已先提交写操作（`row_version` 已变）。"
            "请重新 GET 后再改；`code` 为 `VIDEO_CONFLICT_OPTIMISTIC`。"
        )
    },
}

_CACHE_CONTROL_HEADER: dict[str, Any] = {
    "schema": {"type": "string"},
    "description": (
        "`private, max-age=0, must-revalidate`：避免共享缓存上的陈旧 JSON；"
        "详情在资源变更后应重新验证。"
    ),
}

_VARY_AUTH_HEADER: dict[str, Any] = {
    "schema": {"type": "string"},
    "description": "随 `Authorization` 变化；非发布态仅部分身份可见。",
}

_ETAG_HEADER: dict[str, Any] = {
    "schema": {"type": "string"},
    "description": (
        "弱实体标签（`W/\"…\"`），由 `id`、`updated_at` 与乐观锁 `row_version` 派生；"
        "与 `If-None-Match` 匹配时返回 304。"
    ),
}

VIDEO_LIST_GET_RESPONSES: dict[int, dict[str, Any]] = {
    **BAD_REQUEST_VIDEO,
    **UNAUTH_401,
    **FORBIDDEN_403,
    200: {
        "description": "成功",
        "headers": {
            "X-Total-Count": {
                "schema": {"type": "string"},
                "description": "符合条件的视频总数（与当前页 `limit` 无关）。",
            },
            "X-Has-More": {
                "schema": {"type": "string", "enum": ["true", "false"]},
                "description": "当前页之后是否还有数据（基于 `limit+1` 探测）。",
            },
            "X-Next-Cursor": {
                "schema": {"type": "string"},
                "description": "下一页请求应作为 `cursor` 原样传入；仅当 `X-Has-More` 为 `true` 时出现。",
            },
            "Cache-Control": _CACHE_CONTROL_HEADER,
            "Vary": _VARY_AUTH_HEADER,
        },
    },
}

VIDEO_PLAY_GET_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    **NOT_FOUND_VIDEO,
    **BAD_REQUEST_VIDEO,
    502: {"description": "阿里云 VOD GetVideoPlayAuth 调用失败（`code`：`VOD_API_ERROR`）"},
    503: {"description": "VOD 未配置或 SDK 未安装（`VOD_CONFIG_INCOMPLETE` / `VOD_SDK_NOT_INSTALLED`）"},
    200: {"description": "返回短时 play_auth；勿缓存响应（见 Cache-Control）"},
}

VIDEO_DETAIL_GET_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **NOT_FOUND_VIDEO,
    200: {
        "description": "成功",
        "headers": {
            "Cache-Control": _CACHE_CONTROL_HEADER,
            "Vary": _VARY_AUTH_HEADER,
            "ETag": _ETAG_HEADER,
        },
    },
    304: {
        "description": "资源未修改：请求头 `If-None-Match` 与当前 `ETag` 一致，无响应体。",
        "headers": {
            "Cache-Control": _CACHE_CONTROL_HEADER,
            "Vary": _VARY_AUTH_HEADER,
            "ETag": _ETAG_HEADER,
        },
    },
}

VIDEO_POST_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    **BAD_REQUEST_VIDEO,
    **UNPROCESSABLE_422,
    **IDEMPOTENCY_CONFLICT,
    **IDEMPOTENCY_BACKEND_UNAVAILABLE,
    201: {"description": "已创建，默认 `draft`"},
}

VIDEO_PATCH_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    **BAD_REQUEST_VIDEO,
    **NOT_FOUND_VIDEO,
    **UNPROCESSABLE_422,
    **IDEMPOTENCY_CONFLICT,
    **IDEMPOTENCY_BACKEND_UNAVAILABLE,
    **OPTIMISTIC_CONFLICT_409,
    200: {
        "description": (
            "已更新。**作者自行下架**：`published`→`offline` 可走本 PATCH。"
            "**管理员平台下架**须用 POST `/videos/{video_id}/offline`，勿 PATCH。"
        )
    },
}

VIDEO_BIND_VOD_PATCH_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    **NOT_FOUND_VIDEO,
    **UNPROCESSABLE_422,
    **IDEMPOTENCY_BACKEND_UNAVAILABLE,
    409: {
        "description": (
            "冲突：`VIDEO_VOD_ID_CONFLICT`（该 VOD VideoId 已绑定其它稿件或并发竞态）或 "
            "`VIDEO_VOD_ALREADY_BOUND`（普通用户尝试覆盖已有绑定）或 "
            "`VIDEO_IDEMPOTENCY_CONFLICT`（`Idempotency-Key` 与不同请求体）。"
        )
    },
    200: {"description": "绑定成功，返回视频完整状态"},
}

# 阶段 8.2：审核类 POST（无请求体或 JSON body）
VIDEO_WORKFLOW_POST_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **FORBIDDEN_403,
    **BAD_REQUEST_VIDEO,
    **NOT_FOUND_VIDEO,
    **UNPROCESSABLE_422,
    **OPTIMISTIC_CONFLICT_409,
    200: {"description": "操作成功，返回视频当前完整状态"},
}

VIDEO_WORKFLOW_EVENTS_FORBIDDEN_403: dict[int, dict[str, Any]] = {
    403: {
        "description": (
            "已登录但非本视频作者且非管理员（例如查看他人已发布视频的审计）。"
            "`code`：`VIDEO_WORKFLOW_EVENTS_FORBIDDEN`。"
        )
    },
}

VIDEO_WORKFLOW_EVENTS_GET_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_401,
    **VIDEO_WORKFLOW_EVENTS_FORBIDDEN_403,
    **NOT_FOUND_VIDEO,
    **BAD_REQUEST_VIDEO,
    200: {
        "description": (
            "成功；`X-Total-Count` 为总条数。"
            "当仍有下一页时返回 `X-Has-More` 与 `X-Next-Cursor`（`offset` 首屏或 `cursor` 续页均可拿到游标，续页请改传 `cursor` 且 `offset=0`）。"
        ),
        "headers": {
            "X-Total-Count": {
                "schema": {"type": "string"},
                "description": "符合条件的审计事件总数。",
            },
            "X-Has-More": {
                "schema": {"type": "string", "enum": ["true", "false"]},
                "description": "使用 `cursor` 分页时出现；当前页之后是否还有数据。",
            },
            "X-Next-Cursor": {
                "schema": {"type": "string"},
                "description": "下一页请求作为 `cursor` 传入；仅当 `X-Has-More` 为 `true` 时出现。",
            },
            "Cache-Control": _CACHE_CONTROL_HEADER,
        },
    },
}
