"""evaluation and introductions

Revision ID: 20260307_0007
Revises: 20260307_0006
Create Date: 2026-03-07 18:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0007"
down_revision = "20260307_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("manager_decision_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("interview_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_sessions.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("strengths_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_evaluation_results_match_id", "evaluation_results", ["match_id"], unique=True)
    op.create_index("ix_evaluation_results_status_created_at", "evaluation_results", ["status", "created_at"], unique=False)

    op.create_table(
        "introduction_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("candidate_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("manager_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("introduction_mode", sa.Text(), nullable=False),
        sa.Column("introduced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_introduction_events_match_id", "introduction_events", ["match_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_introduction_events_match_id", table_name="introduction_events")
    op.drop_table("introduction_events")
    op.drop_index("ix_evaluation_results_status_created_at", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_match_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_column("matches", "manager_decision_at")
