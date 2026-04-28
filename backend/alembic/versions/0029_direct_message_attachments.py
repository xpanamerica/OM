"""direct message attachments

Revision ID: 0029_direct_message_attachments
Revises: 0028_user_blocks
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_direct_message_attachments"
down_revision: Union[str, None] = "0028_user_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "direct_message_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("peer_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_filename", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("uploader_id <> peer_id", name="ck_direct_message_attachments_no_self"),
        sa.ForeignKeyConstraint(["peer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_filename", name="uq_direct_message_attachments_storage_filename"),
    )
    op.create_index("ix_direct_message_attachments_uploader", "direct_message_attachments", ["uploader_id"])
    op.create_index("ix_direct_message_attachments_peer", "direct_message_attachments", ["peer_id"])
    op.create_index("ix_direct_message_attachments_created", "direct_message_attachments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_direct_message_attachments_created", table_name="direct_message_attachments")
    op.drop_index("ix_direct_message_attachments_peer", table_name="direct_message_attachments")
    op.drop_index("ix_direct_message_attachments_uploader", table_name="direct_message_attachments")
    op.drop_table("direct_message_attachments")
