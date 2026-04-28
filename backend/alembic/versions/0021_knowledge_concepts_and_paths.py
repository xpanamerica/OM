"""阶段 14：概念节点、视频—概念关联、学习路径

Revision ID: 0021_knowledge_concepts_and_paths
Revises: 0020_upload_intents_table
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_knowledge_concepts_and_paths"
down_revision: Union[str, None] = "0020_upload_intents_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        ts_default = sa.text("now()")
    else:
        ts_default = sa.text("CURRENT_TIMESTAMP")
    bool_false = sa.text("false") if dialect == "postgresql" else sa.text("0")

    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_concepts_name_lower", "concepts", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "video_concepts",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("start_time_seconds", sa.Integer(), nullable=True),
        sa.Column("end_time_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id", "concept_id"),
    )
    op.create_index(op.f("ix_video_concepts_video_id"), "video_concepts", ["video_id"], unique=False)
    op.create_index(op.f("ix_video_concepts_concept_id"), "video_concepts", ["concept_id"], unique=False)

    op.create_table(
        "learning_paths",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=bool_false, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_paths_creator_id"), "learning_paths", ["creator_id"], unique=False)
    op.create_index(op.f("ix_learning_paths_is_published"), "learning_paths", ["is_published"], unique=False)

    op.create_table(
        "learning_path_items",
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("path_id", "order_index"),
    )
    op.create_index(
        "ix_learning_path_items_path_order", "learning_path_items", ["path_id", "order_index"], unique=False
    )
    op.create_index(op.f("ix_learning_path_items_video_id"), "learning_path_items", ["video_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_path_items_video_id"), table_name="learning_path_items")
    op.drop_index("ix_learning_path_items_path_order", table_name="learning_path_items")
    op.drop_table("learning_path_items")
    op.drop_index(op.f("ix_learning_paths_is_published"), table_name="learning_paths")
    op.drop_index(op.f("ix_learning_paths_creator_id"), table_name="learning_paths")
    op.drop_table("learning_paths")
    op.drop_index(op.f("ix_video_concepts_concept_id"), table_name="video_concepts")
    op.drop_index(op.f("ix_video_concepts_video_id"), table_name="video_concepts")
    op.drop_table("video_concepts")
    op.drop_index("ix_concepts_name_lower", table_name="concepts")
    op.drop_table("concepts")
