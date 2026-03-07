from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.core import TimestampMixin, UpdateTimestampMixin


class MatchingRun(Base, TimestampMixin):
    __tablename__ = "matching_runs"
    __table_args__ = (
        Index("ix_matching_runs_vacancy_id_created_at", "vacancy_id", "created_at"),
        Index("ix_matching_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    vacancy_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_candidate_profile_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_pool_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hard_filtered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shortlisted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class Match(Base, UpdateTimestampMixin):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_vacancy_id_status", "vacancy_id", "status"),
        Index("ix_matches_candidate_profile_id_status", "candidate_profile_id", "status"),
        Index("ix_matches_matching_run_id_candidate_profile_id", "matching_run_id", "candidate_profile_id", unique=True),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    matching_run_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matching_runs.id"), nullable=False
    )
    vacancy_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=False
    )
    vacancy_version_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancy_versions.id"), nullable=False
    )
    candidate_profile_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    candidate_profile_version_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profile_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filter_reason_codes_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    embedding_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deterministic_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_rank_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_rank_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rationale_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
