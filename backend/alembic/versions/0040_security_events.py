"""security_events 表（限流等安全事件审计）

Revision ID: 0040_security_events
Revises: 0039_registration_attempts_indexes
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0040_security_events"
down_revision = "0039_registration_attempts_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("subject_hash", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"], unique=False)
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_security_events_created_at", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")
    op.drop_table("security_events")
