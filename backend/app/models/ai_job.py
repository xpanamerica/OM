"""AI 内容处理任务（阶段 15：框架 + Mock 执行器）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AiJobStatus, AiJobType

_ai_job_type_enum = Enum(
    AiJobType,
    name="aijobtype",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
    length=32,
)
_ai_job_status_enum = Enum(
    AiJobStatus,
    name="aijobstatus",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
    length=32,
)


class AiJob(Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (Index("ix_ai_jobs_video_id_created_at", "video_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[AiJobType] = mapped_column(_ai_job_type_enum, nullable=False)
    status: Mapped[AiJobStatus] = mapped_column(
        _ai_job_status_enum,
        nullable=False,
        server_default=AiJobStatus.PENDING.value,
    )
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
