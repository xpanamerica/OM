"""videos 列表常用筛选+排序：(status, created_at) 复合索引

Revision ID: 0009_video_status_created
Revises: 0008_videos
Create Date: 2026-04-23

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009_video_status_created"
down_revision: Union[str, None] = "0008_videos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_videos_status_created_at",
        "videos",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_videos_status_created_at", table_name="videos")
