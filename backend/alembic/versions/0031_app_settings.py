"""app settings

Revision ID: 0031_app_settings
Revises: 0030_user_avatar_url
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_app_settings"
down_revision: Union[str, None] = "0030_user_avatar_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO app_settings (key, value) VALUES "
            "('video_publish_without_review_enabled', 'false')"
        )
    )


def downgrade() -> None:
    op.drop_table("app_settings")
