"""candidate and vacancy matching preferences

Revision ID: 20260312_0012
Revises: 20260311_0011
Create Date: 2026-03-12 15:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260312_0012"
down_revision = "20260311_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidate_profiles", sa.Column("english_level", sa.Text(), nullable=True))
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "preferred_domains_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("candidate_profiles", sa.Column("show_take_home_task_roles", sa.Boolean(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("show_live_coding_roles", sa.Boolean(), nullable=True))

    op.add_column("vacancies", sa.Column("office_city", sa.Text(), nullable=True))
    op.add_column("vacancies", sa.Column("required_english_level", sa.Text(), nullable=True))
    op.add_column(
        "vacancies",
        sa.Column(
            "hiring_stages_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("vacancies", sa.Column("has_take_home_task", sa.Boolean(), nullable=True))
    op.add_column("vacancies", sa.Column("take_home_paid", sa.Boolean(), nullable=True))
    op.add_column("vacancies", sa.Column("has_live_coding", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("vacancies", "has_live_coding")
    op.drop_column("vacancies", "take_home_paid")
    op.drop_column("vacancies", "has_take_home_task")
    op.drop_column("vacancies", "hiring_stages_json")
    op.drop_column("vacancies", "required_english_level")
    op.drop_column("vacancies", "office_city")

    op.drop_column("candidate_profiles", "show_live_coding_roles")
    op.drop_column("candidate_profiles", "show_take_home_task_roles")
    op.drop_column("candidate_profiles", "preferred_domains_json")
    op.drop_column("candidate_profiles", "english_level")
