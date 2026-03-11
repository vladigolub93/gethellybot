from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.cv_challenge import CandidateCvChallengeAttempt


class CandidateCvChallengeAttemptsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        candidate_profile_id,
        candidate_profile_version_id=None,
        skills_snapshot_json: Optional[dict] = None,
        result_json: Optional[dict] = None,
    ) -> CandidateCvChallengeAttempt:
        attempt = CandidateCvChallengeAttempt(
            candidate_profile_id=candidate_profile_id,
            candidate_profile_version_id=candidate_profile_version_id,
            status="started",
            score=0,
            lives_left=3,
            stage_reached=1,
            won=False,
            skills_snapshot_json=skills_snapshot_json or {},
            result_json=result_json,
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def get_by_id(self, attempt_id) -> Optional[CandidateCvChallengeAttempt]:
        stmt = select(CandidateCvChallengeAttempt).where(CandidateCvChallengeAttempt.id == attempt_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_for_candidate_profile(self, candidate_profile_id) -> Optional[CandidateCvChallengeAttempt]:
        stmt = (
            select(CandidateCvChallengeAttempt)
            .where(CandidateCvChallengeAttempt.candidate_profile_id == candidate_profile_id)
            .order_by(CandidateCvChallengeAttempt.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_active_for_candidate_profile(self, candidate_profile_id) -> Optional[CandidateCvChallengeAttempt]:
        stmt = (
            select(CandidateCvChallengeAttempt)
            .where(
                CandidateCvChallengeAttempt.candidate_profile_id == candidate_profile_id,
                CandidateCvChallengeAttempt.finished_at.is_(None),
            )
            .order_by(CandidateCvChallengeAttempt.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_completed_for_candidate_profile(self, candidate_profile_id) -> Optional[CandidateCvChallengeAttempt]:
        stmt = (
            select(CandidateCvChallengeAttempt)
            .where(
                CandidateCvChallengeAttempt.candidate_profile_id == candidate_profile_id,
                CandidateCvChallengeAttempt.finished_at.is_not(None),
            )
            .order_by(CandidateCvChallengeAttempt.finished_at.desc(), CandidateCvChallengeAttempt.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def save_progress(
        self,
        attempt: CandidateCvChallengeAttempt,
        *,
        score: int,
        lives_left: int,
        stage_reached: int,
        progress_json: Optional[dict] = None,
    ) -> CandidateCvChallengeAttempt:
        attempt.status = "started"
        attempt.score = max(int(score), 0)
        attempt.lives_left = max(int(lives_left), 0)
        attempt.stage_reached = max(int(stage_reached), 1)
        if progress_json is not None:
            attempt.result_json = progress_json
        self.session.flush()
        return attempt

    def mark_finished(
        self,
        attempt: CandidateCvChallengeAttempt,
        *,
        score: int,
        lives_left: int,
        stage_reached: int,
        won: bool,
        result_json: Optional[dict] = None,
    ) -> CandidateCvChallengeAttempt:
        attempt.status = "completed"
        attempt.score = max(int(score), 0)
        attempt.lives_left = max(int(lives_left), 0)
        attempt.stage_reached = max(int(stage_reached), 1)
        attempt.won = bool(won)
        attempt.finished_at = datetime.now(timezone.utc)
        if result_json is not None:
            attempt.result_json = result_json
        self.session.flush()
        return attempt
