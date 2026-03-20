"""add admin blocking fields to users

Revision ID: 20260320_0014
Revises: 20260319_0013
Create Date: 2026-03-20 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260320_0014"
down_revision = "20260319_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("blocked_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "is_blocked")
