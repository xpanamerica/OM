"""add user friend requests

Revision ID: 0032_user_friend_requests
Revises: 0031_app_settings
Create Date: 2026-04-28 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0032_user_friend_requests"
down_revision = "0031_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_friend_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("message", sa.String(length=200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("requester_id <> recipient_id", name="ck_user_friend_requests_no_self"),
        sa.CheckConstraint("status in ('pending', 'accepted', 'rejected', 'cancelled')", name="ck_user_friend_requests_status"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_friend_requests_pair_status",
        "user_friend_requests",
        ["requester_id", "recipient_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_user_friend_requests_recipient_status",
        "user_friend_requests",
        ["recipient_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_friend_requests_requester_status",
        "user_friend_requests",
        ["requester_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_friend_requests_requester_status", table_name="user_friend_requests")
    op.drop_index("ix_user_friend_requests_recipient_status", table_name="user_friend_requests")
    op.drop_index("ix_user_friend_requests_pair_status", table_name="user_friend_requests")
    op.drop_table("user_friend_requests")
