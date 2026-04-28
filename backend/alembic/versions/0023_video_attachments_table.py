"""稿件附属文件表（图片/PDF/Office 等）

Revision ID: 0023_video_attachments_table
Revises: 0022_ai_jobs_table
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_video_attachments_table"
down_revision: Union[str, None] = "0022_ai_jobs_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        ts_default = sa.text("now()")
    else:
        ts_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "video_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_filename", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_filename", name="uq_video_attachments_storage_filename"),
    )
    op.create_index(op.f("ix_video_attachments_video_id"), "video_attachments", ["video_id"], unique=False)
    op.create_index(op.f("ix_video_attachments_uploader_id"), "video_attachments", ["uploader_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_attachments_uploader_id"), table_name="video_attachments")
    op.drop_index(op.f("ix_video_attachments_video_id"), table_name="video_attachments")
    op.drop_table("video_attachments")
