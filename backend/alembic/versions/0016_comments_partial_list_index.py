"""comments：部分索引优化「未删除 + 按视频列表」热路径

Revision ID: 0016_comments_partial_list_index
Revises: 0015_comments_table
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_comments_partial_list_index"
down_revision: Union[str, None] = "0015_comments_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "ix_comments_video_created"
_NEW = "ix_comments_video_created_active"


def upgrade() -> None:
    op.drop_index(op.f(_OLD), table_name="comments")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            op.f(_NEW),
            "comments",
            ["video_id", "created_at"],
            unique=False,
            postgresql_where=sa.text("is_deleted IS FALSE"),
        )
    else:
        op.create_index(
            op.f(_NEW),
            "comments",
            ["video_id", "created_at"],
            unique=False,
            sqlite_where=sa.text("is_deleted = 0"),
        )


def downgrade() -> None:
    op.drop_index(op.f(_NEW), table_name="comments")
    op.create_index(
        op.f(_OLD),
        "comments",
        ["video_id", "created_at"],
        unique=False,
    )
