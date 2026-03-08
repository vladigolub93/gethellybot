"""add vacancy summary review fields

Revision ID: 20260308_0010
Revises: 20260307_0009
Create Date: 2026-03-08 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260308_0010"
down_revision = "20260307_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancy_versions", sa.Column("approval_summary_text", sa.Text(), nullable=True))
    op.add_column(
        "vacancy_versions",
        sa.Column(
            "approval_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
    )
    op.add_column(
        "vacancy_versions",
        sa.Column(
            "approved_by_manager",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("vacancy_versions", "approved_by_manager")
    op.drop_column("vacancy_versions", "approval_status")
    op.drop_column("vacancy_versions", "approval_summary_text")
