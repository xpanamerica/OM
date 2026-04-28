from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserPrivacySetting(Base):
    """用户互动隐私设置。"""

    __tablename__ = "user_privacy_settings"
    __table_args__ = (
        CheckConstraint(
            "profile_visibility IN ('public', 'followers', 'mutual', 'private')",
            name="ck_user_privacy_profile_visibility",
        ),
        CheckConstraint(
            "message_permission IN ('everyone', 'following', 'mutual', 'none')",
            name="ck_user_privacy_message_permission",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_visibility: Mapped[str] = mapped_column(String(16), nullable=False, server_default="public")
    message_permission: Mapped[str] = mapped_column(String(16), nullable=False, server_default="everyone")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
