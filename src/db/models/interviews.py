from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.core import TimestampMixin, UpdateTimestampMixin


class InterviewSession(Base, UpdateTimestampMixin):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        Index("ix_interview_sessions_match_id", "match_id", unique=True),
        Index("ix_interview_sessions_candidate_profile_id_state", "candidate_profile_id", "state"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False
    )
    candidate_profile_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    vacancy_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    current_question_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    total_questions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class InterviewQuestion(Base, TimestampMixin):
    __tablename__ = "interview_questions"
    __table_args__ = (
        Index("ix_interview_questions_session_id_order_no", "session_id", "order_no", unique=True),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False
    )
    order_no: Mapped[int] = mapped_column(nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_kind: Mapped[str] = mapped_column(Text, nullable=False)
    parent_question_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_questions.id"), nullable=True
    )
    asked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewAnswer(Base, TimestampMixin):
    __tablename__ = "interview_answers"
    __table_args__ = (
        Index("ix_interview_answers_question_id_created_at", "question_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False
    )
    question_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_questions.id"), nullable=False
    )
    raw_message_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_messages.id"), nullable=True
    )
    file_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_follow_up_answer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
