"""upload_intents：VOD 上传凭证意图审计（阶段 12）

Revision ID: 0020_upload_intents_table
Revises: 0019_videos_vod_columns
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_upload_intents_table"
down_revision: Union[str, None] = "0019_videos_vod_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "upload_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("vod_video_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="issued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_upload_intents_user_id"), "upload_intents", ["user_id"], unique=False)
    op.create_index(
        "ix_upload_intents_user_id_created_at",
        "upload_intents",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_upload_intents_user_id_created_at", table_name="upload_intents")
    op.drop_index(op.f("ix_upload_intents_user_id"), table_name="upload_intents")
    op.drop_table("upload_intents")
