"""candidate work formats json

Revision ID: 20260319_0013
Revises: 20260312_0012
Create Date: 2026-03-19 09:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0013"
down_revision = "20260312_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "work_formats_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        update candidate_profiles
        set work_formats_json = jsonb_build_array(lower(work_format))
        where work_format is not null
          and trim(work_format) <> ''
          and lower(work_format) in ('remote', 'hybrid', 'office')
        """
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "work_formats_json")
