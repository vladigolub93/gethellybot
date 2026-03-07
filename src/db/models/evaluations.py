from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.core import TimestampMixin


class EvaluationResult(Base, TimestampMixin):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        Index("ix_evaluation_results_match_id", "match_id", unique=True),
        Index("ix_evaluation_results_status_created_at", "status", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False
    )
    interview_session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    strengths_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    risks_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSONB, nullable=False)


class IntroductionEvent(Base, TimestampMixin):
    __tablename__ = "introduction_events"
    __table_args__ = (
        Index("ix_introduction_events_match_id", "match_id", unique=True),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False
    )
    candidate_user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    manager_user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    introduction_mode: Mapped[str] = mapped_column(Text, nullable=False)
    introduced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
