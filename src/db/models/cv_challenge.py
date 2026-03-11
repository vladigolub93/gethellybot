from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.core import TimestampMixin


class CandidateCvChallengeAttempt(Base, TimestampMixin):
    __tablename__ = "candidate_cv_challenge_attempts"
    __table_args__ = (
        Index(
            "ix_candidate_cv_challenge_attempts_profile_id_created_at",
            "candidate_profile_id",
            "created_at",
        ),
        Index(
            "ix_candidate_cv_challenge_attempts_profile_id_finished_at",
            "candidate_profile_id",
            "finished_at",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    candidate_profile_version_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profile_versions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'started'"))
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lives_left: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    stage_reached: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    won: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    skills_snapshot_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
