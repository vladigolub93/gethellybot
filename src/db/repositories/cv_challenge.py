from __future__ import annotations

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

    def get_best_completed_for_candidate_profile(self, candidate_profile_id) -> Optional[CandidateCvChallengeAttempt]:
        stmt = (
            select(CandidateCvChallengeAttempt)
            .where(
                CandidateCvChallengeAttempt.candidate_profile_id == candidate_profile_id,
                CandidateCvChallengeAttempt.finished_at.is_not(None),
            )
        )
        attempts = list(self.session.execute(stmt).scalars().all())
        if not attempts:
            return None

        def sort_key(attempt: CandidateCvChallengeAttempt) -> tuple:
            result_json = attempt.result_json if isinstance(attempt.result_json, dict) else {}
            total_mistakes = result_json.get("totalMistakes")
            try:
                parsed_mistakes = int(total_mistakes)
            except (TypeError, ValueError):
                parsed_mistakes = 10**9

            finished_at_ts = attempt.finished_at.timestamp() if attempt.finished_at else 0
            created_at_ts = attempt.created_at.timestamp() if attempt.created_at else 0
            return (
                -max(int(attempt.score or 0), 0),
                -max(int(attempt.stage_reached or 1), 1),
                parsed_mistakes,
                -finished_at_ts,
                -created_at_ts,
            )

        attempts.sort(key=sort_key)
        return attempts[0]

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
