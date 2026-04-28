"""骨架占位 revision（无表变更）；业务表在后续阶段加入。

Revision ID: 0001_skeleton_placeholder
Revises:
Create Date: 2026-04-22

"""

from typing import Sequence, Union

revision: str = "0001_skeleton_placeholder"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
