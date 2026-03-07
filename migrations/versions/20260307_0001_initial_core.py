"""initial core schema

Revision ID: 20260307_0001
Revises:
Create Date: 2026-03-07 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector";')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("language_code", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("is_candidate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_hiring_manager", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=False)

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("telegram_file_id", sa.Text(), nullable=True),
        sa.Column("telegram_unique_file_id", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("extension", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_files_owner_user_id", "files", ["owner_user_id"], unique=False)
    op.create_index("ix_files_kind", "files", ["kind"], unique=False)
    op.create_index("ix_files_telegram_unique_file_id", "files", ["telegram_unique_file_id"], unique=False)

    op.create_table(
        "raw_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("telegram_update_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_raw_messages_telegram_update_id",
        "raw_messages",
        ["telegram_update_id"],
        unique=True,
        postgresql_where=sa.text("telegram_update_id IS NOT NULL"),
    )
    op.create_index("ix_raw_messages_user_id_created_at", "raw_messages", ["user_id", "created_at"], unique=False)
    op.create_index(
        "ix_raw_messages_telegram_chat_id_created_at",
        "raw_messages",
        ["telegram_chat_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("consent_type", sa.Text(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=True),
        sa.Column("source_raw_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_messages.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_user_consents_user_id_consent_type_granted_at",
        "user_consents",
        ["user_id", "consent_type", "granted_at"],
        unique=False,
    )

    op.create_table(
        "state_transition_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("trigger_ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_state_transition_logs_entity_type_entity_id_created_at",
        "state_transition_logs",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_state_transition_logs_trigger_type", "state_transition_logs", ["trigger_type"], unique=False)

    op.create_table(
        "job_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_job_execution_logs_job_type_idempotency_key_attempt_no",
        "job_execution_logs",
        ["job_type", "idempotency_key", "attempt_no"],
        unique=True,
    )
    op.create_index("ix_job_execution_logs_status_queued_at", "job_execution_logs", ["status", "queued_at"], unique=False)
    op.create_index("ix_job_execution_logs_entity_type_entity_id", "job_execution_logs", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("send_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_status_send_after", "notifications", ["status", "send_after"], unique=False)
    op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"], unique=False)

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_outbox_events_status_available_at", "outbox_events", ["status", "available_at"], unique=False)
    op.create_index("ix_outbox_events_entity_type_entity_id", "outbox_events", ["entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_outbox_events_entity_type_entity_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_available_at", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status_send_after", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_job_execution_logs_entity_type_entity_id", table_name="job_execution_logs")
    op.drop_index("ix_job_execution_logs_status_queued_at", table_name="job_execution_logs")
    op.drop_index("ix_job_execution_logs_job_type_idempotency_key_attempt_no", table_name="job_execution_logs")
    op.drop_table("job_execution_logs")

    op.drop_index("ix_state_transition_logs_trigger_type", table_name="state_transition_logs")
    op.drop_index("ix_state_transition_logs_entity_type_entity_id_created_at", table_name="state_transition_logs")
    op.drop_table("state_transition_logs")

    op.drop_index("ix_user_consents_user_id_consent_type_granted_at", table_name="user_consents")
    op.drop_table("user_consents")

    op.drop_index("ix_raw_messages_telegram_chat_id_created_at", table_name="raw_messages")
    op.drop_index("ix_raw_messages_user_id_created_at", table_name="raw_messages")
    op.drop_index("ix_raw_messages_telegram_update_id", table_name="raw_messages")
    op.drop_table("raw_messages")

    op.drop_index("ix_files_telegram_unique_file_id", table_name="files")
    op.drop_index("ix_files_kind", table_name="files")
    op.drop_index("ix_files_owner_user_id", table_name="files")
    op.drop_table("files")

    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_index("ix_users_telegram_user_id", table_name="users")
    op.drop_table("users")

