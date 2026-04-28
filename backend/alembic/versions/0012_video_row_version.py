"""videos 增加 row_version 乐观并发

Revision ID: 0012_video_row_version
Revises: 0011_video_workflow_events
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_video_row_version"
down_revision: Union[str, None] = "0011_video_workflow_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("videos", "row_version")
