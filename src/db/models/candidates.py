from datetime import datetime
from typing import List, Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from src.db.base import Base
from src.db.models.core import TimestampMixin, UpdateTimestampMixin
from src.embeddings.constants import DEFAULT_EMBEDDING_DIMENSIONS


class CandidateProfile(Base, UpdateTimestampMixin):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        Index("ix_candidate_profiles_state", "state"),
        Index(
            "ix_candidate_profiles_user_id_active",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profile_versions.id"), nullable=True
    )
    salary_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    salary_period: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    work_format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    english_level: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_domains_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    show_take_home_task_roles: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    show_live_coding_roles: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    questions_context_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    seniority_normalized: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateProfileVersion(Base, TimestampMixin):
    __tablename__ = "candidate_profile_versions"
    __table_args__ = (
        Index(
            "ix_candidate_profile_versions_profile_id_version_no",
            "profile_id",
            "version_no",
            unique=True,
        ),
        Index(
            "ix_candidate_profile_versions_profile_id_created_at",
            "profile_id",
            "created_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True
    )
    source_raw_message_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_messages.id"), nullable=True
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    semantic_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(DEFAULT_EMBEDDING_DIMENSIONS),
        nullable=True,
    )
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    normalization_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    approved_by_user: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CandidateVerification(Base, TimestampMixin):
    __tablename__ = "candidate_verifications"
    __table_args__ = (
        Index(
            "ix_candidate_verifications_profile_id_attempt_no",
            "profile_id",
            "attempt_no",
            unique=True,
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(nullable=False)
    phrase_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    video_file_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
