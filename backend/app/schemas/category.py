from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy_text import normalize_taxonomy_description, normalize_taxonomy_name


class CategoryPublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        description="展示用名称；写入前经 NFKC 与 trim；唯一性大小写不敏感（lower(name) 唯一索引）。",
    )
    description: str | None = Field(
        default=None,
        max_length=512,
        description="可选；写入前经 NFKC 与 trim，空串存为 null。",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return normalize_taxonomy_name(v)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, v: str | None) -> str | None:
        return normalize_taxonomy_description(v)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(
        default=None,
        max_length=512,
        description="可选；写入前经 NFKC 与 trim，空串存为 null。",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_taxonomy_name(v)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, v: str | None) -> str | None:
        return normalize_taxonomy_description(v)
