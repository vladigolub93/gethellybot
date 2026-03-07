"""add invite waves

Revision ID: 20260307_0009
Revises: 20260307_0008
Create Date: 2026-03-07 21:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260307_0009"
down_revision = "20260307_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_waves",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column(
            "matching_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matching_runs.id"),
            nullable=False,
        ),
        sa.Column("wave_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("invited_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_interviews_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_invites_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invite_waves_vacancy_id_created_at",
        "invite_waves",
        ["vacancy_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_invite_waves_matching_run_id_wave_no",
        "invite_waves",
        ["matching_run_id", "wave_no"],
        unique=True,
    )
    op.create_index(
        "ix_invite_waves_status_created_at",
        "invite_waves",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invite_waves_status_created_at", table_name="invite_waves")
    op.drop_index("ix_invite_waves_matching_run_id_wave_no", table_name="invite_waves")
    op.drop_index("ix_invite_waves_vacancy_id_created_at", table_name="invite_waves")
    op.drop_table("invite_waves")
