"""分类/标签名称改为大小写不敏感唯一（lower(name) 唯一索引）

Revision ID: 0006_taxonomy_ci_unique
Revises: 0005_categories_tags
Create Date: 2026-04-23

PostgreSQL 与 SQLite 均支持 `CREATE UNIQUE INDEX ... (lower(name))`。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_taxonomy_ci_unique"
down_revision: Union[str, None] = "0005_categories_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_categories_name"), table_name="categories")
    op.drop_index(op.f("ix_tags_name"), table_name="tags")
    op.execute(
        sa.text("CREATE UNIQUE INDEX ix_categories_name_lower ON categories (lower(name))")
    )
    op.execute(sa.text("CREATE UNIQUE INDEX ix_tags_name_lower ON tags (lower(name))"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_categories_name_lower"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_tags_name_lower"))
    op.create_index(op.f("ix_categories_name"), "categories", ["name"], unique=True)
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=True)
