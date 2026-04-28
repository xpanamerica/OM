"""分类 / 标签 HTTP 层共用常量（缓存策略等）。

最终策略说明见 `http_cache_control.MUTABLE_GET_CACHE_CONTROL`。
"""

from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL

TAXONOMY_LIST_CACHE_CONTROL = MUTABLE_GET_CACHE_CONTROL
