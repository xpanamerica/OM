from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.knowledge_text import normalize_concept_description, normalize_concept_name
from app.schemas.video import VideoListItem


class ConceptPublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConceptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def v_name(cls, v: str) -> str:
        return normalize_concept_name(v)

    @field_validator("description")
    @classmethod
    def v_desc(cls, v: str | None) -> str | None:
        return normalize_concept_description(v)


class ConceptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def v_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_concept_name(v)

    @field_validator("description")
    @classmethod
    def v_desc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_concept_description(v)


class VideoConceptLink(BaseModel):
    concept_id: uuid.UUID
    start_time_seconds: int | None = Field(default=None, ge=0)
    end_time_seconds: int | None = Field(default=None, ge=0)


class VideoConceptsPut(BaseModel):
    items: list[VideoConceptLink] = Field(default_factory=list)


class VideoConceptPublic(BaseModel):
    concept_id: uuid.UUID
    concept_name: str
    start_time_seconds: int | None
    end_time_seconds: int | None

    model_config = {"from_attributes": False}


class ConceptLinkedVideoOut(VideoListItem):
    """概念下已发布视频 + 管理员标注的片段时间（秒）。"""

    model_config = ConfigDict(extra="forbid")

    start_time_seconds: int | None = Field(
        default=None,
        description="在该视频中与该概念关联的片段起点（秒）；未标则 null。",
    )
    end_time_seconds: int | None = Field(
        default=None,
        description="片段终点（秒）；未标则 null。",
    )
