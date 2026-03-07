"""matching foundation

Revision ID: 20260307_0005
Revises: 20260307_0004
Create Date: 2026-03-07 17:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0005"
down_revision = "20260307_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matching_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column(
            "trigger_candidate_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidate_profiles.id"),
            nullable=True,
        ),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("candidate_pool_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hard_filtered_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("shortlisted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_matching_runs_vacancy_id_created_at", "matching_runs", ["vacancy_id", "created_at"], unique=False)
    op.create_index("ix_matching_runs_status_created_at", "matching_runs", ["status", "created_at"], unique=False)

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("matching_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matching_runs.id"), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("vacancy_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancy_versions.id"), nullable=False),
        sa.Column("candidate_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id"), nullable=False),
        sa.Column("candidate_profile_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profile_versions.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column("filter_reason_codes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("embedding_score", sa.Float(), nullable=True),
        sa.Column("deterministic_score", sa.Float(), nullable=True),
        sa.Column("llm_rank_score", sa.Float(), nullable=True),
        sa.Column("llm_rank_position", sa.Integer(), nullable=True),
        sa.Column("rationale_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_matches_vacancy_id_status", "matches", ["vacancy_id", "status"], unique=False)
    op.create_index("ix_matches_candidate_profile_id_status", "matches", ["candidate_profile_id", "status"], unique=False)
    op.create_index("ix_matches_matching_run_id_candidate_profile_id", "matches", ["matching_run_id", "candidate_profile_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_matches_matching_run_id_candidate_profile_id", table_name="matches")
    op.drop_index("ix_matches_candidate_profile_id_status", table_name="matches")
    op.drop_index("ix_matches_vacancy_id_status", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_matching_runs_status_created_at", table_name="matching_runs")
    op.drop_index("ix_matching_runs_vacancy_id_created_at", table_name="matching_runs")
    op.drop_table("matching_runs")
