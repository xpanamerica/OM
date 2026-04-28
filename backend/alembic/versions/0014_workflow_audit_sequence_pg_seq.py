"""PostgreSQL：audit_sequence 改为 SEQUENCE 默认值，降低高并发下 MAX+1 竞争

Revision ID: 0014_workflow_audit_sequence_pg_seq
Revises: 0013_video_workflow_audit_sequence
Create Date: 2026-04-23

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0014_workflow_audit_sequence_pg_seq"
down_revision: Union[str, None] = "0013_video_workflow_audit_sequence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEQ = "sq_video_workflow_events_audit_seq"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    bind.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {_SEQ}"))
    # PostgreSQL：setval 不允许 0（序列合法范围为 1..max）；空表或全 0 时用 1。
    bind.execute(
        text(
            f"""
            SELECT setval(
                '{_SEQ}',
                GREATEST(
                    1,
                    COALESCE((SELECT MAX(audit_sequence) FROM video_workflow_events), 0)
                )
            )
            """
        )
    )
    bind.execute(
        text(
            f"""
            ALTER TABLE video_workflow_events
            ALTER COLUMN audit_sequence SET DEFAULT nextval('{_SEQ}')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    bind.execute(
        text(
            """
            ALTER TABLE video_workflow_events
            ALTER COLUMN audit_sequence DROP DEFAULT
            """
        )
    )
    bind.execute(text(f"DROP SEQUENCE IF EXISTS {_SEQ}"))
