"""comments：视频一级评论（软删除）

Revision ID: 0015_comments_table
Revises: 0014_workflow_audit_sequence_pg_seq
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_comments_table"
down_revision: Union[str, None] = "0014_workflow_audit_sequence_pg_seq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")
    # PostgreSQL：BOOLEAN 的 server_default 须为 true/false，不能用 0/1
    bool_false = sa.text("false") if dialect == "postgresql" else sa.text("0")

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_user_id"), "comments", ["user_id"], unique=False)
    op.create_index(op.f("ix_comments_video_id"), "comments", ["video_id"], unique=False)
    op.create_index(
        op.f("ix_comments_video_created"),
        "comments",
        ["video_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_comments_video_created"), table_name="comments")
    op.drop_index(op.f("ix_comments_video_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_user_id"), table_name="comments")
    op.drop_table("comments")
