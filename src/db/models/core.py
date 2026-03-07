from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UpdateTimestampMixin(TimestampMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class User(Base, UpdateTimestampMixin):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_hiring_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    consents = relationship("UserConsent", back_populates="user")


class File(Base, UpdateTimestampMixin):
    __tablename__ = "files"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telegram_unique_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extension: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RawMessage(Base, TimestampMixin):
    __tablename__ = "raw_messages"
    __table_args__ = (
        Index(
            "ix_raw_messages_telegram_update_id",
            "telegram_update_id",
            unique=True,
            postgresql_where=text("telegram_update_id IS NOT NULL"),
        ),
        Index("ix_raw_messages_user_id_created_at", "user_id", "created_at"),
        Index("ix_raw_messages_telegram_chat_id_created_at", "telegram_chat_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    telegram_update_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True
    )
    correlation_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True)


class UserConsent(Base, TimestampMixin):
    __tablename__ = "user_consents"
    __table_args__ = (
        Index(
            "ix_user_consents_user_id_consent_type_granted_at",
            "user_id",
            "consent_type",
            "granted_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    consent_type: Mapped[str] = mapped_column(Text, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_raw_message_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_messages.id"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="consents")


class StateTransitionLog(Base, TimestampMixin):
    __tablename__ = "state_transition_logs"
    __table_args__ = (
        Index(
            "ix_state_transition_logs_entity_type_entity_id_created_at",
            "entity_type",
            "entity_id",
            "created_at",
        ),
        Index("ix_state_transition_logs_trigger_type", "trigger_type"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_ref_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)


class JobExecutionLog(Base):
    __tablename__ = "job_execution_logs"
    __table_args__ = (
        Index(
            "ix_job_execution_logs_job_type_idempotency_key_attempt_no",
            "job_type",
            "idempotency_key",
            "attempt_no",
            unique=True,
        ),
        Index("ix_job_execution_logs_status_queued_at", "status", "queued_at"),
        Index("ix_job_execution_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON_VARIANT, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base, UpdateTimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_status_send_after", "status", "send_after"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    template_key: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    send_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_available_at", "status", "available_at"),
        Index("ix_outbox_events_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
