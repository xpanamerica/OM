"""video_workflow_events：审核/平台下架工作流审计

Revision ID: 0011_video_workflow_events
Revises: 0010_video_rejection_reason
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_video_workflow_events"
down_revision: Union[str, None] = "0010_video_rejection_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    ts_default = sa.text("now()") if dialect == "postgresql" else sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "video_workflow_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_video_workflow_events_video_id"), "video_workflow_events", ["video_id"], unique=False)
    op.create_index(op.f("ix_video_workflow_events_actor_id"), "video_workflow_events", ["actor_id"], unique=False)
    op.create_index(
        op.f("ix_video_workflow_events_video_created"),
        "video_workflow_events",
        ["video_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_video_workflow_events_video_created"), table_name="video_workflow_events")
    op.drop_index(op.f("ix_video_workflow_events_actor_id"), table_name="video_workflow_events")
    op.drop_index(op.f("ix_video_workflow_events_video_id"), table_name="video_workflow_events")
    op.drop_table("video_workflow_events")
