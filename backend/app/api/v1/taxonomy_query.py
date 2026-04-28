"""分类 / 标签列表共用的分页查询参数。"""

import uuid
from typing import Annotated

from fastapi import Query

from app.core.taxonomy_cursor import encode_taxonomy_cursor

_OPENAPI_CURSOR_EXAMPLE = encode_taxonomy_cursor(
    name="demo",
    row_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
)

TaxonomyListLimit = Annotated[
    int | None,
    Query(
        ge=1,
        le=500,
        description="可选分页大小；省略则返回全部记录（此时忽略 offset）。",
    ),
]

TaxonomyListOffset = Annotated[
    int,
    Query(
        ge=0,
        le=1_000_000,
        description="与 limit 同时使用时生效的分页偏移；与 cursor 互斥。",
    ),
]

TaxonomyListCursor = Annotated[
    str | None,
    Query(
        max_length=512,
        description=(
            "可选键集游标（上一页末行或响应头 `X-Next-Cursor`）；"
            "须与 limit 同用且不得与 offset 同用。"
        ),
        openapi_examples={
            "none": {"summary": "首屏", "value": None},
            "next": {"summary": "续页", "value": _OPENAPI_CURSOR_EXAMPLE},
        },
    ),
]
