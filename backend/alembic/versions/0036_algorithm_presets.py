"""add user algorithm presets

Revision ID: 0036_algorithm_presets
Revises: 0035_attention_value
Create Date: 2026-04-29 00:46:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0036_algorithm_presets"
down_revision = "0035_attention_value"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_algorithm_presets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_algorithm_presets_user_created",
        "user_algorithm_presets",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_algorithm_presets_user_name",
        "user_algorithm_presets",
        ["user_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_algorithm_presets_user_name", table_name="user_algorithm_presets")
    op.drop_index("ix_user_algorithm_presets_user_created", table_name="user_algorithm_presets")
    op.drop_table("user_algorithm_presets")
