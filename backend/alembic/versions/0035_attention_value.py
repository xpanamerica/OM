"""add attention value snapshots

Revision ID: 0035_attention_value
Revises: 0034_algorithm_modes
Create Date: 2026-04-29 00:24:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0035_attention_value"
down_revision = "0034_algorithm_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attention_value_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm_mode", sa.String(length=32), nullable=False),
        sa.Column("input_quality", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cognitive_growth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attention_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attention_snapshots_user_created", "attention_value_snapshots", ["user_id", "created_at"], unique=False)
    op.create_index("ix_attention_snapshots_mode", "attention_value_snapshots", ["algorithm_mode"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attention_snapshots_mode", table_name="attention_value_snapshots")
    op.drop_index("ix_attention_snapshots_user_created", table_name="attention_value_snapshots")
    op.drop_table("attention_value_snapshots")
