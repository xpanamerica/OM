from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAlgorithmState(Base):
    __tablename__ = "user_algorithm_states"
    __table_args__ = (
        Index("ix_user_algorithm_states_user_id", "user_id", unique=True),
        Index("ix_user_algorithm_states_mode", "mode"),
        Index("ix_user_algorithm_states_personalized", "personalized"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, server_default="personalized")
    personalized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    exploration_seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cold_start_strategy: Mapped[str] = mapped_column(String(64), nullable=False, server_default="personalized")
    algorithm_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attention_index: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AlgorithmResetLog(Base):
    __tablename__ = "algorithm_reset_logs"
    __table_args__ = (
        Index("ix_algorithm_reset_logs_user_reset_at", "user_id", "reset_at"),
        Index("ix_algorithm_reset_logs_type_status", "reset_type", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reset_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="one_click_origin")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_tables: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AttentionValueSnapshot(Base):
    __tablename__ = "attention_value_snapshots"
    __table_args__ = (
        Index("ix_attention_snapshots_user_created", "user_id", "created_at"),
        Index("ix_attention_snapshots_mode", "algorithm_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    algorithm_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    input_quality: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cognitive_growth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    time_quality: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    information_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    propagation_impact: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deep_engagement: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attention_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserAlgorithmPreset(Base):
    __tablename__ = "user_algorithm_presets"
    __table_args__ = (
        Index("ix_user_algorithm_presets_user_created", "user_id", "created_at"),
        Index("ix_user_algorithm_presets_user_name", "user_id", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(240), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
