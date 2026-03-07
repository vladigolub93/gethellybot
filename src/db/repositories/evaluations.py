from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.evaluations import EvaluationResult, IntroductionEvent


class EvaluationsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_match_id(self, match_id) -> Optional[EvaluationResult]:
        stmt = select(EvaluationResult).where(EvaluationResult.match_id == match_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        match_id,
        interview_session_id,
        status: str,
        final_score: float,
        strengths_json: list,
        risks_json: list,
        recommendation: str,
        report_json: dict,
    ) -> EvaluationResult:
        row = EvaluationResult(
            match_id=match_id,
            interview_session_id=interview_session_id,
            status=status,
            final_score=final_score,
            strengths_json=strengths_json,
            risks_json=risks_json,
            recommendation=recommendation,
            report_json=report_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_introduction_event(
        self,
        *,
        match_id,
        candidate_user_id,
        manager_user_id,
        introduction_mode: str,
        status: str = "introduced",
    ) -> IntroductionEvent:
        row = IntroductionEvent(
            match_id=match_id,
            candidate_user_id=candidate_user_id,
            manager_user_id=manager_user_id,
            status=status,
            introduction_mode=introduction_mode,
            introduced_at=datetime.now(timezone.utc),
        )
        self.session.add(row)
        self.session.flush()
        return row
