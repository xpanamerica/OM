"""稿件附属文件 API 模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VideoAttachmentOut(BaseModel):
    id: UUID
    original_filename: str
    content_type: str | None
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}
