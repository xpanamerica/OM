from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy_text import normalize_taxonomy_name


class TagPublic(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        description="展示用名称；写入前经 NFKC 与 trim；唯一性大小写不敏感。",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return normalize_taxonomy_name(v)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_taxonomy_name(v)
