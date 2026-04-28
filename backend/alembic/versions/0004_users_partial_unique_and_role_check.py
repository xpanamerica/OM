"""部分唯一索引（未软删）+ role 数据库 CHECK

Revision ID: 0004_users_constraints
Revises: 0003_users_role
Create Date: 2026-04-22

SQLite 不支持直接 ALTER TABLE 添加 CHECK，需使用 batch_alter_table 的表重建路径；
PostgreSQL 使用标准 create_check_constraint。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_users_constraints"
down_revision: Union[str, None] = "0003_users_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_partial_unique_indexes() -> None:
    op.create_index(
        "ix_users_email_alive",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_users_username_alive",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def upgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.create_check_constraint(
            "ck_users_role",
            "users",
            sa.text("role IN ('user', 'admin')"),
        )
    elif dialect == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_check_constraint(
                "ck_users_role",
                sa.text("role IN ('user', 'admin')"),
            )
    else:
        op.create_check_constraint(
            "ck_users_role",
            "users",
            sa.text("role IN ('user', 'admin')"),
        )

    if dialect in ("postgresql", "sqlite"):
        _create_partial_unique_indexes()
    else:
        op.create_index(op.f("ix_users_email_alive"), "users", ["email"], unique=True)
        op.create_index(op.f("ix_users_username_alive"), "users", ["username"], unique=True)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect in ("postgresql", "sqlite"):
        op.drop_index("ix_users_username_alive", table_name="users")
        op.drop_index("ix_users_email_alive", table_name="users")

    if dialect == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
    elif dialect == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_constraint("ck_users_role", type_="check")
    else:
        op.drop_constraint("ck_users_role", "users", type_="check")

    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
