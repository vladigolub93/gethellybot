"""interview foundation

Revision ID: 20260307_0006
Revises: 20260307_0005
Create Date: 2026-03-07 17:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0006"
down_revision = "20260307_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("invitation_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("candidate_response_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("candidate_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidate_profiles.id"), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("current_question_order", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_sessions_match_id", "interview_sessions", ["match_id"], unique=True)
    op.create_index("ix_interview_sessions_candidate_profile_id_state", "interview_sessions", ["candidate_profile_id", "state"], unique=False)

    op.create_table(
        "interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_sessions.id"), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_kind", sa.Text(), nullable=False),
        sa.Column("parent_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_questions.id"), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_questions_session_id_order_no", "interview_questions", ["session_id", "order_no"], unique=True)

    op.create_table(
        "interview_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_sessions.id"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_questions.id"), nullable=False),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id"), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("is_follow_up_answer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interview_answers_question_id_created_at", "interview_answers", ["question_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_answers_question_id_created_at", table_name="interview_answers")
    op.drop_table("interview_answers")
    op.drop_index("ix_interview_questions_session_id_order_no", table_name="interview_questions")
    op.drop_table("interview_questions")
    op.drop_index("ix_interview_sessions_candidate_profile_id_state", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_match_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
    op.drop_column("matches", "candidate_response_at")
    op.drop_column("matches", "invitation_sent_at")
