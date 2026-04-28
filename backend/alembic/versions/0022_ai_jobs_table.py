"""阶段 15：AI 内容处理任务表

Revision ID: 0022_ai_jobs_table
Revises: 0021_knowledge_concepts_and_paths
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_ai_jobs_table"
down_revision: Union[str, None] = "0021_knowledge_concepts_and_paths"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        ts_default = sa.text("now()")
    else:
        ts_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_jobs_video_id"), "ai_jobs", ["video_id"], unique=False)
    op.create_index("ix_ai_jobs_video_id_created_at", "ai_jobs", ["video_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_video_id_created_at", table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_video_id"), table_name="ai_jobs")
    op.drop_table("ai_jobs")
