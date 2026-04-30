"""MFA、会话字段与 JWT kid 支持

Revision ID: 0044_mfa_sessions_jwt_keys
Revises: 0043_auth_state_security_event_fields
Create Date: 2026-04-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0044_mfa_sessions_jwt_keys"
down_revision = "0043_auth_state_security_event_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    bool_false = sa.text("false") if dialect == "postgresql" else sa.text("0")

    op.create_table(
        "user_mfa_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("totp_secret_sealed", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=bool_false, nullable=False),
        sa.Column("recovery_code_hashes_json", sa.Text(), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.add_column("refresh_tokens", sa.Column("device_label", sa.String(length=128), nullable=True))
    op.add_column("refresh_tokens", sa.Column("user_agent_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("refresh_tokens", "user_agent_hash")
    op.drop_column("refresh_tokens", "device_label")
    op.drop_table("user_mfa_settings")
