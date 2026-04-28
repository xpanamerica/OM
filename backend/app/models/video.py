from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Table, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VideoStatus, VodTranscodeStatus, VodUploadStatus

_video_status_enum = Enum(
    VideoStatus,
    name="videostatus",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
    length=32,
)

_vod_upload_enum = Enum(
    VodUploadStatus,
    name="voduploadstatus",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
    length=32,
)

_vod_transcode_enum = Enum(
    VodTranscodeStatus,
    name="vodtranscodestatus",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
    length=32,
)

video_tags = Table(
    "video_tags",
    Base.metadata,
    Column("video_id", Uuid(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Uuid(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_status_created_at", "status", "created_at"),
        Index(
            "uq_videos_vod_video_id",
            "vod_video_id",
            unique=True,
            postgresql_where=text("vod_video_id IS NOT NULL"),
            sqlite_where=text("vod_video_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        _video_status_enum,
        nullable=False,
        server_default=VideoStatus.DRAFT.value,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    views_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    likes_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    favorites_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_video_relpath: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vod_video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upload_status: Mapped[VodUploadStatus] = mapped_column(
        _vod_upload_enum,
        nullable=False,
        server_default=VodUploadStatus.NOT_STARTED.value,
    )
    transcode_status: Mapped[VodTranscodeStatus] = mapped_column(
        _vod_transcode_enum,
        nullable=False,
        server_default=VodTranscodeStatus.NONE.value,
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": row_version}

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary=video_tags,
        lazy="selectin",
        order_by="Tag.name",
    )
