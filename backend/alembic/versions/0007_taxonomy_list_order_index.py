"""列表按 (name, id) 排序时的复合索引，减轻大表 OFFSET/键集分页压力

Revision ID: 0007_taxonomy_list_idx
Revises: 0006_taxonomy_ci_unique
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007_taxonomy_list_idx"
down_revision: Union[str, None] = "0006_taxonomy_ci_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_categories_name_id_list",
        "categories",
        ["name", "id"],
        unique=False,
    )
    op.create_index(
        "ix_tags_name_id_list",
        "tags",
        ["name", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tags_name_id_list", table_name="tags")
    op.drop_index("ix_categories_name_id_list", table_name="categories")
