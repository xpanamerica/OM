"""videos 表增加本机成片相对路径（免阿里云亦可播放）

Revision ID: 0024_videos_local_video_relpath
Revises: 0023_video_attachments_table
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_videos_local_video_relpath"
down_revision: Union[str, None] = "0023_video_attachments_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("local_video_relpath", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "local_video_relpath")
