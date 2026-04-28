"""add formal attention value factors

Revision ID: 0037_attention_value_factors
Revises: 0036_algorithm_presets
Create Date: 2026-04-29 00:56:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0037_attention_value_factors"
down_revision = "0036_algorithm_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attention_value_snapshots", sa.Column("time_quality", sa.Integer(), server_default="0", nullable=False))
    op.add_column("attention_value_snapshots", sa.Column("information_value", sa.Integer(), server_default="0", nullable=False))
    op.add_column("attention_value_snapshots", sa.Column("propagation_impact", sa.Integer(), server_default="0", nullable=False))
    op.add_column("attention_value_snapshots", sa.Column("deep_engagement", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("attention_value_snapshots", "deep_engagement")
    op.drop_column("attention_value_snapshots", "propagation_impact")
    op.drop_column("attention_value_snapshots", "information_value")
    op.drop_column("attention_value_snapshots", "time_quality")
