"""可变业务数据的 GET 响应缓存策略（列表/详情等）。

与分类/标签列表一致：禁止 public 短缓存，避免 CDN 陈旧 JSON。
"""

from starlette.responses import Response

# 与 taxonomy_http.TAXONOMY_LIST_CACHE_CONTROL 语义相同，供视频等非 taxonomy 路由复用。
MUTABLE_GET_CACHE_CONTROL = "private, max-age=0, must-revalidate"

# 评论列表：禁止浏览器磁盘缓存，避免带 If-None-Match 拿到 304 时部分客户端出现空 body。
COMMENT_LIST_CACHE_CONTROL = "private, no-store, max-age=0"

# 写操作响应：禁止缓存，避免代理/浏览器误存个性化 JSON。
MUTATION_RESPONSE_CACHE_CONTROL = "private, no-store"


def set_mutation_cache_control(response: Response) -> None:
    """作为 `Depends(...)` 挂在 POST/PATCH/DELETE 等写路由上。"""
    response.headers["Cache-Control"] = MUTATION_RESPONSE_CACHE_CONTROL
