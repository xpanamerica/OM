"""add algorithm modes and attention controls

Revision ID: 0034_algorithm_modes
Revises: 0033_algorithm_reset
Create Date: 2026-04-29 00:12:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0034_algorithm_modes"
down_revision = "0033_algorithm_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_algorithm_states", sa.Column("algorithm_parameters", sa.JSON(), nullable=True))
    op.add_column("user_algorithm_states", sa.Column("attention_index", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("user_algorithm_states", "attention_index")
    op.drop_column("user_algorithm_states", "algorithm_parameters")
