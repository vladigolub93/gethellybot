from datetime import datetime
from typing import List, Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from src.db.base import Base
from src.db.models.core import TimestampMixin, UpdateTimestampMixin
from src.embeddings.constants import DEFAULT_EMBEDDING_DIMENSIONS


class Vacancy(Base, UpdateTimestampMixin):
    __tablename__ = "vacancies"
    __table_args__ = (
        Index("ix_vacancies_state", "state"),
        Index("ix_vacancies_manager_user_id_created_at", "manager_user_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    manager_user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancy_versions.id"), nullable=True
    )
    role_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seniority_normalized: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_currency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_period: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    countries_allowed_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    work_format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    team_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    project_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_tech_stack_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    questions_context_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class VacancyVersion(Base, TimestampMixin):
    __tablename__ = "vacancy_versions"
    __table_args__ = (
        Index("ix_vacancy_versions_vacancy_id_version_no", "vacancy_id", "version_no", unique=True),
        Index("ix_vacancy_versions_vacancy_id_created_at", "vacancy_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    vacancy_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=False
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
    approval_summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    normalization_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    inconsistency_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    approval_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    approved_by_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
