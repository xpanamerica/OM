"""indexes for registration_attempts (audit list / abuse lookup)

Revision ID: 0039_registration_attempts_indexes
Revises: 0038_invite_codes_registration
Create Date: 2026-04-29
"""

from __future__ import annotations

from alembic import op


revision = "0039_registration_attempts_indexes"
down_revision = "0038_invite_codes_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_registration_attempts_created_at",
        "registration_attempts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_registration_attempts_ip_created",
        "registration_attempts",
        ["ip_address", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_registration_attempts_ip_created", table_name="registration_attempts")
    op.drop_index("ix_registration_attempts_created_at", table_name="registration_attempts")
