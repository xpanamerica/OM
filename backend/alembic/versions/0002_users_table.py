"""创建 users 表

Revision ID: 0002_users
Revises: 0001_skeleton_placeholder
Create Date: 2026-04-22

PostgreSQL 与 SQLite 对布尔默认值、时间函数语法不同，此处按方言分支，保证
`alembic upgrade head` 在 CI（SQLite 文件）与生产（PostgreSQL）均可执行。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_users"
down_revision: Union[str, None] = "0001_skeleton_placeholder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        bool_true = sa.text("true")
        bool_false = sa.text("false")
        ts_default = sa.text("now()")
    else:
        # SQLite：无 now() 函数；布尔常用 0/1
        bool_true = sa.text("1")
        bool_false = sa.text("0")
        ts_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=bool_true, nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default=bool_false, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=ts_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=ts_default,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
