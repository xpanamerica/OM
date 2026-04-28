"""video_workflow_events：全局单调 audit_sequence，用于键集分页 tie-break

Revision ID: 0013_video_workflow_audit_sequence
Revises: 0012a_widen_alembic_ver
Create Date: 2026-04-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0013_video_workflow_audit_sequence"
down_revision: Union[str, None] = "0012a_widen_alembic_ver"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.add_column(
            "video_workflow_events",
            sa.Column("audit_sequence", sa.Integer(), nullable=False, server_default="0"),
        )
    else:
        op.add_column(
            "video_workflow_events",
            sa.Column("audit_sequence", sa.Integer(), nullable=True),
        )

    bind.execute(
        text(
            """
            UPDATE video_workflow_events AS v
            SET audit_sequence = n.rn
            FROM (
                SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS rn
                FROM video_workflow_events
            ) AS n
            WHERE v.id = n.id
            """
        )
    )

    # SQLite 旧版不支持 ALTER COLUMN … DROP DEFAULT；保留 server_default=0，应用层始终写入序号。
    if dialect != "sqlite":
        op.alter_column(
            "video_workflow_events",
            "audit_sequence",
            existing_type=sa.Integer(),
            nullable=False,
        )

    if dialect == "sqlite":
        op.create_index(
            "uq_video_workflow_events_audit_sequence",
            "video_workflow_events",
            ["audit_sequence"],
            unique=True,
        )
    else:
        op.create_unique_constraint(
            "uq_video_workflow_events_audit_sequence",
            "video_workflow_events",
            ["audit_sequence"],
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.drop_index("uq_video_workflow_events_audit_sequence", table_name="video_workflow_events")
    else:
        op.drop_constraint("uq_video_workflow_events_audit_sequence", "video_workflow_events", type_="unique")
    op.drop_column("video_workflow_events", "audit_sequence")
