"""用受约束的 role 枚举列替代 is_superuser

Revision ID: 0003_users_role
Revises: 0002_users
Create Date: 2026-04-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_users_role"
down_revision: Union[str, None] = "0002_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
    )
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE is_superuser"))
    op.drop_column("users", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(sa.text("UPDATE users SET is_superuser = (role = 'admin')"))
    op.drop_column("users", "role")
