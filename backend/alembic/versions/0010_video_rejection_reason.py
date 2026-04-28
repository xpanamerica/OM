"""videos 表增加 rejection_reason（驳回说明）

Revision ID: 0010_video_rejection_reason
Revises: 0009_video_status_created
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_video_rejection_reason"
down_revision: Union[str, None] = "0009_video_status_created"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "rejection_reason")
