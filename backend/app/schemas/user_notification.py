from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserNotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str | None = None
    kind: str = Field(default="info")
    action_url: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class UserNotificationUnreadCount(BaseModel):
    unread_count: int
