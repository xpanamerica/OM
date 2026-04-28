"""video_likes / video_favorites 与 (user_id, video_id) 唯一约束

Revision ID: 0017_video_likes_and_favorites
Revises: 0016_comments_partial_list_index
Create Date: 2026-04-23

``videos.likes_count`` / ``videos.favorites_count`` 由应用层在
``app.services.video_interaction_service`` 中随插入/删除同步更新
（见 ``app.services.video_statistics_service.adjust_likes_count`` /
``adjust_favorites_count``），
便于 SQLite 内存测试（``create_all``）与生产共用一套逻辑。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_video_likes_and_favorites"
down_revision: Union[str, None] = "0016_comments_partial_list_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "video_likes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_video_likes_user_video"),
    )
    op.create_index(op.f("ix_video_likes_video_id"), "video_likes", ["video_id"], unique=False)
    op.create_index(op.f("ix_video_likes_user_id"), "video_likes", ["user_id"], unique=False)

    op.create_table(
        "video_favorites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_video_favorites_user_video"),
    )
    op.create_index(op.f("ix_video_favorites_video_id"), "video_favorites", ["video_id"], unique=False)
    op.create_index(op.f("ix_video_favorites_user_id"), "video_favorites", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_favorites_user_id"), table_name="video_favorites")
    op.drop_index(op.f("ix_video_favorites_video_id"), table_name="video_favorites")
    op.drop_table("video_favorites")
    op.drop_index(op.f("ix_video_likes_user_id"), table_name="video_likes")
    op.drop_index(op.f("ix_video_likes_video_id"), table_name="video_likes")
    op.drop_table("video_likes")
