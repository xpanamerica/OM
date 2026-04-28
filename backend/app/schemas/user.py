import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    avatar_url: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
