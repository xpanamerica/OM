"""认证状态与安全事件结构化字段

Revision ID: 0043_auth_state_security_event_fields
Revises: 0042_refresh_tokens
Create Date: 2026-04-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0043_auth_state_security_event_fields"
down_revision = "0042_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    op.create_table(
        "user_auth_states",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_login_window_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_user_auth_states_locked_until", "user_auth_states", ["locked_until"], unique=False)

    op.add_column("security_events", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("security_events", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("security_events", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column("security_events", sa.Column("metadata_json", sa.Text(), nullable=True))
    op.create_index("ix_security_events_user_created", "security_events", ["user_id", "created_at"], unique=False)
    op.create_index(
        "ix_security_events_subject_created",
        "security_events",
        ["subject_hash", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_subject_created", table_name="security_events")
    op.drop_index("ix_security_events_user_created", table_name="security_events")
    op.drop_column("security_events", "metadata_json")
    op.drop_column("security_events", "user_agent")
    op.drop_column("security_events", "request_id")
    op.drop_column("security_events", "user_id")
    op.drop_index("ix_user_auth_states_locked_until", table_name="user_auth_states")
    op.drop_table("user_auth_states")
