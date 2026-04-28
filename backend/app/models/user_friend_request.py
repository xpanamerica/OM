from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFriendRequest(Base):
    """用户好友申请：同意后会自动建立双向关注关系。"""

    __tablename__ = "user_friend_requests"
    __table_args__ = (
        CheckConstraint("requester_id <> recipient_id", name="ck_user_friend_requests_no_self"),
        CheckConstraint("status in ('pending', 'accepted', 'rejected', 'cancelled')", name="ck_user_friend_requests_status"),
        Index("ix_user_friend_requests_pair_status", "requester_id", "recipient_id", "status"),
        Index("ix_user_friend_requests_recipient_status", "recipient_id", "status", "created_at"),
        Index("ix_user_friend_requests_requester_status", "requester_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
