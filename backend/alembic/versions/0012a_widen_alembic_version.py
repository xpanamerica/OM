"""加宽 alembic_version.version_num，避免长 revision id 写入失败（PostgreSQL VARCHAR(32)）

Revision ID: 0012a_widen_alembic_ver
Revises: 0012_video_row_version
Create Date: 2026-04-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012a_widen_alembic_ver"
down_revision: Union[str, None] = "0012_video_row_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
    )


def downgrade() -> None:
    # 回缩为 VARCHAR(32) 在长 revision 已写入时会失败，故不在此自动收缩。
    pass
