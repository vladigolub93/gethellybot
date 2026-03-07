from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models.candidates import CandidateVerification


class CandidateVerificationsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_pending_by_profile_id(self, profile_id) -> Optional[CandidateVerification]:
        stmt = (
            select(CandidateVerification)
            .where(
                CandidateVerification.profile_id == profile_id,
                CandidateVerification.status == "issued",
            )
            .order_by(CandidateVerification.attempt_no.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def next_attempt_no(self, profile_id) -> int:
        stmt = select(func.coalesce(func.max(CandidateVerification.attempt_no), 0)).where(
            CandidateVerification.profile_id == profile_id
        )
        current_max = self.session.execute(stmt).scalar_one()
        return int(current_max) + 1

    def create(self, *, profile_id, attempt_no: int, phrase_text: str, status: str = "issued") -> CandidateVerification:
        row = CandidateVerification(
            profile_id=profile_id,
            attempt_no=attempt_no,
            phrase_text=phrase_text,
            status=status,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def mark_submitted(self, verification: CandidateVerification, *, video_file_id) -> CandidateVerification:
        verification.status = "submitted"
        verification.video_file_id = video_file_id
        verification.submitted_at = datetime.now(timezone.utc)
        self.session.flush()
        return verification

    def list_for_profile(self, profile_id) -> list[CandidateVerification]:
        stmt = select(CandidateVerification).where(
            CandidateVerification.profile_id == profile_id
        )
        return list(self.session.execute(stmt).scalars().all())
