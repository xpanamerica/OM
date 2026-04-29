from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminInviteCodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_at: datetime | None = Field(default=None, description="为空表示不设过期时间")
    max_uses: int = Field(default=1, ge=1, le=100_000, description="默认可用 1 次（一次性邀请码）")


class AdminInviteCodeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    created_by: uuid.UUID | None
    used_by: uuid.UUID | None
    used_at: datetime | None
    expires_at: datetime | None
    max_uses: int
    used_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class AdminInviteCodeListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminInviteCodeItem]
    total: int = Field(ge=0)


class AdminInviteCodeCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite: AdminInviteCodeItem = Field(description="新建记录；``code`` 为明文，请妥善保存。")


class RegistrationOptionsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite_code_required: bool = Field(description="为 True 时须凭有效邀请码注册。")


class AdminRegistrationAttemptItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: str
    user_agent: str | None
    email: str | None
    username: str | None
    invite_code_submitted: str | None
    success: bool
    failure_reason: str | None
    created_user_id: uuid.UUID | None
    created_at: datetime


class AdminRegistrationAttemptListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminRegistrationAttemptItem]
    total: int = Field(ge=0)
