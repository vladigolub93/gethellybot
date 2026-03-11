"""add cv challenge attempts

Revision ID: 20260311_0011
Revises: 20260308_0010
Create Date: 2026-03-11 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260311_0011"
down_revision = "20260308_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_cv_challenge_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_profile_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'started'"), nullable=False),
        sa.Column("score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lives_left", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("stage_reached", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("won", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skills_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profiles.id"], name=op.f("fk_candidate_cv_challenge_attempts_candidate_profile_id_candidate_profiles")),
        sa.ForeignKeyConstraint(["candidate_profile_version_id"], ["candidate_profile_versions.id"], name=op.f("fk_candidate_cv_challenge_attempts_candidate_profile_version_id_candidate_profile_versions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_cv_challenge_attempts")),
    )
    op.create_index(
        "ix_candidate_cv_challenge_attempts_profile_id_created_at",
        "candidate_cv_challenge_attempts",
        ["candidate_profile_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_cv_challenge_attempts_profile_id_finished_at",
        "candidate_cv_challenge_attempts",
        ["candidate_profile_id", "finished_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_cv_challenge_attempts_profile_id_finished_at", table_name="candidate_cv_challenge_attempts")
    op.drop_index("ix_candidate_cv_challenge_attempts_profile_id_created_at", table_name="candidate_cv_challenge_attempts")
    op.drop_table("candidate_cv_challenge_attempts")
