"""视频列表分页查询参数（与 taxonomy 规则对齐）。"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Query

from app.core.video_cursor import encode_video_list_cursor, encode_workflow_audit_cursor

_OPENAPI_CURSOR_EXAMPLE = encode_video_list_cursor(
    created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    row_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
)

_WORKFLOW_AUDIT_CURSOR_EXAMPLE = encode_workflow_audit_cursor(
    created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    audit_sequence=42,
)

VideoListLimit = Annotated[
    int,
    Query(
        ge=1,
        le=500,
        description="分页大小；与 `offset` 做偏移分页，或与 `cursor` 做键集续页（二者互斥）。",
    ),
]

VideoListOffset = Annotated[
    int,
    Query(
        ge=0,
        le=1_000_000,
        description="与 `limit` 联用的偏移；与 `cursor` 互斥。",
    ),
]

VideoListCursor = Annotated[
    str | None,
    Query(
        max_length=512,
        description=(
            "键集续页：上一页末行对应 `X-Next-Cursor`；须与 `limit` 同用且 `offset` 须为 0。"
        ),
        openapi_examples={
            "none": {"summary": "首屏", "value": None},
            "next": {"summary": "续页", "value": _OPENAPI_CURSOR_EXAMPLE},
        },
    ),
]

# 工作流审计列表：独立游标编码（`created_at` + 全局单调 `audit_sequence`，与视频 id 游标不同）
WorkflowAuditOffset = Annotated[
    int,
    Query(
        ge=0,
        le=500_000,
        description="与 `limit` 联用的偏移；与 `cursor` 互斥。",
    ),
]

WorkflowAuditLimit = Annotated[
    int,
    Query(
        ge=1,
        le=200,
        description="分页大小；与 `offset` 或 `cursor`+`limit` 联用。",
    ),
]

WorkflowAuditCursor = Annotated[
    str | None,
    Query(
        max_length=512,
        description=(
            "键集续页：取上一页响应头 `X-Next-Cursor`；须与 `limit` 同用且 `offset` 须为 0。"
            "载荷为 `created_at` + 全局单调 `audit_sequence`（非事件 UUID，避免同秒续页乱序）。"
        ),
        openapi_examples={
            "none": {"summary": "首屏", "value": None},
            "next": {"summary": "续页", "value": _WORKFLOW_AUDIT_CURSOR_EXAMPLE},
        },
    ),
]
