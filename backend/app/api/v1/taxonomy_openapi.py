"""分类 / 标签路由共用的 OpenAPI 片段（中文说明与常见 HTTP 状态）。"""

from typing import Any

UNAUTH_OR_FORBIDDEN: dict[int, dict[str, Any]] = {
    401: {"description": "未认证或令牌无效"},
    403: {"description": "需要管理员权限"},
}

NAME_CONFLICT: dict[int, dict[str, Any]] = {
    409: {"description": "名称已存在（与已有记录冲突；比较为大小写不敏感）"},
}

BAD_REQUEST_PAGINATION: dict[int, dict[str, Any]] = {
    400: {
        "description": (
            "分页参数无效或冲突："
            "未指定 limit 却使用 offset；"
            "使用 cursor 时必须指定 limit；"
            "不可同时使用 cursor 与 offset；"
            "cursor 解码或载荷无效。"
        )
    },
}

LIST_GET_RESPONSES: dict[int, dict[str, Any]] = {
    400: BAD_REQUEST_PAGINATION[400],
    200: {
        "description": "成功",
        "headers": {
            "X-Has-More": {
                "schema": {"type": "string", "enum": ["true", "false"]},
                "description": "仅当请求携带 `limit` 时返回：是否还有下一页。",
            },
            "X-Next-Cursor": {
                "schema": {"type": "string"},
                "description": (
                    "下一页应作为 `cursor` 查询参数原样传入；"
                    "仅当 `X-Has-More` 为 `true` 时返回。"
                ),
            },
            "Cache-Control": {
                "schema": {"type": "string"},
                "description": (
                    "`private, max-age=0, must-revalidate`：列表可被管理员修改，"
                    "避免共享缓存上的陈旧 JSON；浏览器默认不长期缓存响应体。"
                ),
            },
        },
    },
}

NOT_FOUND_CATEGORY: dict[int, dict[str, Any]] = {
    404: {"description": "分类不存在"},
}

NOT_FOUND_TAG: dict[int, dict[str, Any]] = {
    404: {"description": "标签不存在"},
}

ADMIN_CREATE_RESPONSES: dict[int, dict[str, Any]] = {
    **UNAUTH_OR_FORBIDDEN,
    **NAME_CONFLICT,
}
