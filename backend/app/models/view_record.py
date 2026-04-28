from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ViewRecord(Base):
    """用户对视频的播放进度；``(user_id, video_id)`` 唯一一行。"""

    __tablename__ = "view_records"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_view_records_user_video"),
        CheckConstraint("progress_seconds >= 0", name="ck_view_records_progress_nonnegative"),
        Index("ix_view_records_user_id", "user_id"),
        Index("ix_view_records_video_id", "video_id"),
        Index("ix_view_records_user_last_viewed", "user_id", "last_viewed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    progress_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
