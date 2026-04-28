"""videos：阿里云 VOD 媒资绑定字段（阶段 11.2）

Revision ID: 0019_videos_vod_columns
Revises: 0018_view_records_table
Create Date: 2026-04-26

- ``vod_video_id``：非空时全局唯一（部分唯一索引，允许多行 NULL）
- ``upload_status`` / ``transcode_status``：字符串枚举落库，与 ``app.models.enums`` 一致
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_videos_vod_columns"
down_revision: Union[str, None] = "0018_view_records_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("vod_video_id", sa.String(length=128), nullable=True))
    op.add_column(
        "videos",
        sa.Column(
            "upload_status",
            sa.String(length=32),
            server_default="not_started",
            nullable=False,
        ),
    )
    op.add_column(
        "videos",
        sa.Column(
            "transcode_status",
            sa.String(length=32),
            server_default="none",
            nullable=False,
        ),
    )
    op.add_column("videos", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("source_file_name", sa.String(length=512), nullable=True))

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.create_index(
            "uq_videos_vod_video_id",
            "videos",
            ["vod_video_id"],
            unique=True,
            postgresql_where=sa.text("vod_video_id IS NOT NULL"),
        )
    else:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_videos_vod_video_id ON videos (vod_video_id) "
                "WHERE vod_video_id IS NOT NULL"
            )
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.drop_index("uq_videos_vod_video_id", table_name="videos")
    else:
        op.execute(sa.text("DROP INDEX IF EXISTS uq_videos_vod_video_id"))

    op.drop_column("videos", "source_file_name")
    op.drop_column("videos", "duration_seconds")
    op.drop_column("videos", "transcode_status")
    op.drop_column("videos", "upload_status")
    op.drop_column("videos", "vod_video_id")
