"""创建 videos 与 video_tags（多对多）

Revision ID: 0008_videos
Revises: 0007_taxonomy_list_idx
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_videos"
down_revision: Union[str, None] = "0007_taxonomy_list_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        int0 = sa.text("0")
        ts_default = sa.text("now()")
    else:
        int0 = sa.text("0")
        ts_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "videos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("video_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("views_count", sa.Integer(), server_default=int0, nullable=False),
        sa.Column("likes_count", sa.Integer(), server_default=int0, nullable=False),
        sa.Column("favorites_count", sa.Integer(), server_default=int0, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=ts_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=ts_default,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_videos_author_id"), "videos", ["author_id"], unique=False)
    op.create_index(op.f("ix_videos_category_id"), "videos", ["category_id"], unique=False)
    op.create_index(op.f("ix_videos_status"), "videos", ["status"], unique=False)
    op.create_index(op.f("ix_videos_created_at"), "videos", ["created_at"], unique=False)

    op.create_table(
        "video_tags",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("video_tags")
    op.drop_index(op.f("ix_videos_created_at"), table_name="videos")
    op.drop_index(op.f("ix_videos_status"), table_name="videos")
    op.drop_index(op.f("ix_videos_category_id"), table_name="videos")
    op.drop_index(op.f("ix_videos_author_id"), table_name="videos")
    op.drop_table("videos")
