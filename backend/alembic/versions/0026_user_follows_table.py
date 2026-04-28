"""user_follows：用户关注（个人中心 关注/粉丝）

Revision ID: 0026_user_follows_table
Revises: 0025_user_notifications_table
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_user_follows_table"
down_revision: Union[str, None] = "0025_user_notifications_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followee_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_user_follows_no_self"),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_user_follows_pair"),
    )
    op.create_index("ix_user_follows_follower", "user_follows", ["follower_id"], unique=False)
    op.create_index("ix_user_follows_followee", "user_follows", ["followee_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_follows_followee", table_name="user_follows")
    op.drop_index("ix_user_follows_follower", table_name="user_follows")
    op.drop_table("user_follows")
