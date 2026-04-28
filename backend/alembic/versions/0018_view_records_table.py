"""view_records：每用户每视频一条播放进度；首条创建时 ``views_count`` 在应用层 +1

Revision ID: 0018_view_records_table
Revises: 0017_video_likes_and_favorites
Create Date: 2026-04-24

``videos.views_count`` 仅在首次插入 ``view_records`` 时由
``app.services.video_statistics_service.increment_views_count`` 原子递增（见 ``view_record_service``）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_view_records_table"
down_revision: Union[str, None] = "0017_video_likes_and_favorites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "view_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("progress_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.CheckConstraint("progress_seconds >= 0", name="ck_view_records_progress_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_view_records_user_video"),
    )
    op.create_index(op.f("ix_view_records_video_id"), "view_records", ["video_id"], unique=False)
    op.create_index(op.f("ix_view_records_user_id"), "view_records", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_view_records_user_last_viewed"),
        "view_records",
        ["user_id", "last_viewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_view_records_user_last_viewed"), table_name="view_records")
    op.drop_index(op.f("ix_view_records_user_id"), table_name="view_records")
    op.drop_index(op.f("ix_view_records_video_id"), table_name="view_records")
    op.drop_table("view_records")
