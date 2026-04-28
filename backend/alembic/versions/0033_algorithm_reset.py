"""add algorithm reset state and logs

Revision ID: 0033_algorithm_reset
Revises: 0032_user_friend_requests
Create Date: 2026-04-28 23:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0033_algorithm_reset"
down_revision = "0032_user_friend_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_algorithm_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=32), server_default="personalized", nullable=False),
        sa.Column("personalized", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("exploration_seed", sa.String(length=64), nullable=True),
        sa.Column("cold_start_strategy", sa.String(length=64), server_default="personalized", nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_algorithm_states_user_id", "user_algorithm_states", ["user_id"], unique=True)
    op.create_index("ix_user_algorithm_states_mode", "user_algorithm_states", ["mode"], unique=False)
    op.create_index("ix_user_algorithm_states_personalized", "user_algorithm_states", ["personalized"], unique=False)

    op.create_table(
        "algorithm_reset_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reset_type", sa.String(length=64), server_default="one_click_origin", nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("affected_tables", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_algorithm_reset_logs_user_reset_at", "algorithm_reset_logs", ["user_id", "reset_at"], unique=False)
    op.create_index("ix_algorithm_reset_logs_type_status", "algorithm_reset_logs", ["reset_type", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_algorithm_reset_logs_type_status", table_name="algorithm_reset_logs")
    op.drop_index("ix_algorithm_reset_logs_user_reset_at", table_name="algorithm_reset_logs")
    op.drop_table("algorithm_reset_logs")
    op.drop_index("ix_user_algorithm_states_personalized", table_name="user_algorithm_states")
    op.drop_index("ix_user_algorithm_states_mode", table_name="user_algorithm_states")
    op.drop_index("ix_user_algorithm_states_user_id", table_name="user_algorithm_states")
    op.drop_table("user_algorithm_states")
