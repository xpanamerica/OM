from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.knowledge_text import (
    normalize_learning_path_description,
    normalize_learning_path_title,
)
from app.schemas.video import VideoListItem


class LearningPathItemWrite(BaseModel):
    video_id: uuid.UUID
    order_index: int = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=2000)


class LearningPathCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    is_published: bool = False
    items: list[LearningPathItemWrite] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def v_title(cls, v: str) -> str:
        return normalize_learning_path_title(v)

    @field_validator("description")
    @classmethod
    def v_desc(cls, v: str | None) -> str | None:
        return normalize_learning_path_description(v)


class LearningPathUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    is_published: bool | None = None

    @field_validator("title")
    @classmethod
    def v_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_learning_path_title(v)

    @field_validator("description")
    @classmethod
    def v_desc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_learning_path_description(v)


class LearningPathPublic(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    creator_id: uuid.UUID
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LearningPathItemPublic(BaseModel):
    order_index: int
    video_id: uuid.UUID
    note: str | None
    video: VideoListItem | None = None


class LearningPathDetail(LearningPathPublic):
    items: list[LearningPathItemPublic] = Field(default_factory=list)


class LearningPathItemsPut(BaseModel):
    items: list[LearningPathItemWrite] = Field(default_factory=list)
