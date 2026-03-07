"""vacancy foundation

Revision ID: 20260307_0004
Revises: 20260307_0003
Create Date: 2026-03-07 16:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0004"
down_revision = "20260307_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("manager_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_title", sa.Text(), nullable=True),
        sa.Column("seniority_normalized", sa.Text(), nullable=True),
        sa.Column("budget_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("budget_currency", sa.Text(), nullable=True),
        sa.Column("budget_period", sa.Text(), nullable=True),
        sa.Column("countries_allowed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("work_format", sa.Text(), nullable=True),
        sa.Column("team_size", sa.Integer(), nullable=True),
        sa.Column("project_description", sa.Text(), nullable=True),
        sa.Column("primary_tech_stack_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("questions_context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_vacancies_state", "vacancies", ["state"], unique=False)
    op.create_index("ix_vacancies_manager_user_id_created_at", "vacancies", ["manager_user_id", "created_at"], unique=False)

    op.create_table(
        "vacancy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("source_raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id"), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalization_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("inconsistency_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_vacancy_versions_vacancy_id_version_no", "vacancy_versions", ["vacancy_id", "version_no"], unique=True)
    op.create_index("ix_vacancy_versions_vacancy_id_created_at", "vacancy_versions", ["vacancy_id", "created_at"], unique=False)
    op.create_foreign_key(
        "fk_vacancies_current_version_id_vacancy_versions",
        "vacancies",
        "vacancy_versions",
        ["current_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_vacancies_current_version_id_vacancy_versions", "vacancies", type_="foreignkey")
    op.drop_index("ix_vacancy_versions_vacancy_id_created_at", table_name="vacancy_versions")
    op.drop_index("ix_vacancy_versions_vacancy_id_version_no", table_name="vacancy_versions")
    op.drop_table("vacancy_versions")
    op.drop_index("ix_vacancies_manager_user_id_created_at", table_name="vacancies")
    op.drop_index("ix_vacancies_state", table_name="vacancies")
    op.drop_table("vacancies")
