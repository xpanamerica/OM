from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AiJobStatus, AiJobType

_JOB_TYPES = frozenset(e.value for e in AiJobType)


class AiJobCreate(BaseModel):
    job_type: str = Field(
        description="``transcript`` | ``summary`` | ``concept_extract`` | ``chapter_extract``",
    )
    input_payload: dict[str, Any] | None = Field(default=None, description="可选 JSON，供后续真实模型使用")

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        s = (v or "").strip().lower()
        if s not in _JOB_TYPES:
            raise ValueError(f"job_type 须为之一: {', '.join(sorted(_JOB_TYPES))}")
        return s


class AiJobPublic(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    job_type: AiJobType
    status: AiJobStatus = Field(
        description=(
            "``pending`` → ``processing``（执行中，文档中常写作 running）→ "
            "``completed``（成功，常写作 success）或 ``failed``"
        )
    )
    input_payload: dict[str, Any] | None
    output_payload: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
