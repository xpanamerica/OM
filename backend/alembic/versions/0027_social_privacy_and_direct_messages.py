"""social privacy and direct messages

Revision ID: 0027_social_privacy_and_direct_messages
Revises: 0026_user_follows_table
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_social_privacy_and_direct_messages"
down_revision: Union[str, None] = "0026_user_follows_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    op.create_table(
        "user_privacy_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_visibility", sa.String(length=16), server_default="public", nullable=False),
        sa.Column("message_permission", sa.String(length=16), server_default="everyone", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.CheckConstraint(
            "profile_visibility IN ('public', 'followers', 'mutual', 'private')",
            name="ck_user_privacy_profile_visibility",
        ),
        sa.CheckConstraint(
            "message_permission IN ('everyone', 'following', 'mutual', 'none')",
            name="ck_user_privacy_message_permission",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "direct_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_low_id", sa.Uuid(), nullable=False),
        sa.Column("participant_high_id", sa.Uuid(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.CheckConstraint(
            "participant_low_id <> participant_high_id",
            name="ck_direct_conversations_no_self",
        ),
        sa.ForeignKeyConstraint(["participant_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_low_id",
            "participant_high_id",
            name="uq_direct_conversations_pair",
        ),
    )
    op.create_index("ix_direct_conversations_low", "direct_conversations", ["participant_low_id"])
    op.create_index("ix_direct_conversations_high", "direct_conversations", ["participant_high_id"])
    op.create_index("ix_direct_conversations_last", "direct_conversations", ["last_message_at"])
    op.create_table(
        "direct_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["direct_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_direct_messages_conversation_created",
        "direct_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_direct_messages_recipient_read", "direct_messages", ["recipient_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_direct_messages_recipient_read", table_name="direct_messages")
    op.drop_index("ix_direct_messages_conversation_created", table_name="direct_messages")
    op.drop_table("direct_messages")
    op.drop_index("ix_direct_conversations_last", table_name="direct_conversations")
    op.drop_index("ix_direct_conversations_high", table_name="direct_conversations")
    op.drop_index("ix_direct_conversations_low", table_name="direct_conversations")
    op.drop_table("direct_conversations")
    op.drop_table("user_privacy_settings")
