"""candidate profile foundation

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07 12:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0002"
down_revision = "20260307_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.Text(), nullable=True),
        sa.Column("salary_period", sa.Text(), nullable=True),
        sa.Column("location_text", sa.Text(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("work_format", sa.Text(), nullable=True),
        sa.Column("seniority_normalized", sa.Text(), nullable=True),
        sa.Column("target_role", sa.Text(), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_candidate_profiles_state", "candidate_profiles", ["state"], unique=False)
    op.create_index(
        "ix_candidate_profiles_user_id_active",
        "candidate_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "candidate_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("source_raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id"), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalization_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("approval_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("approved_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_candidate_profile_versions_profile_id_version_no",
        "candidate_profile_versions",
        ["profile_id", "version_no"],
        unique=True,
    )
    op.create_index(
        "ix_candidate_profile_versions_profile_id_created_at",
        "candidate_profile_versions",
        ["profile_id", "created_at"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_candidate_profiles_current_version_id_candidate_profile_versions",
        "candidate_profiles",
        "candidate_profile_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "candidate_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("phrase_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("video_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_candidate_verifications_profile_id_attempt_no",
        "candidate_verifications",
        ["profile_id", "attempt_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_verifications_profile_id_attempt_no", table_name="candidate_verifications")
    op.drop_table("candidate_verifications")

    op.drop_constraint(
        "fk_candidate_profiles_current_version_id_candidate_profile_versions",
        "candidate_profiles",
        type_="foreignkey",
    )

    op.drop_index("ix_candidate_profile_versions_profile_id_created_at", table_name="candidate_profile_versions")
    op.drop_index("ix_candidate_profile_versions_profile_id_version_no", table_name="candidate_profile_versions")
    op.drop_table("candidate_profile_versions")

    op.drop_index("ix_candidate_profiles_user_id_active", table_name="candidate_profiles")
    op.drop_index("ix_candidate_profiles_state", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")

