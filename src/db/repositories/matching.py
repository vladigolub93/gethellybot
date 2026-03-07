from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.matching import Match, MatchingRun


class MatchingRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_run(
        self,
        *,
        vacancy_id,
        trigger_type: str,
        trigger_candidate_profile_id=None,
        status: str = "running",
        payload_json: Optional[dict] = None,
    ) -> MatchingRun:
        row = MatchingRun(
            vacancy_id=vacancy_id,
            trigger_type=trigger_type,
            trigger_candidate_profile_id=trigger_candidate_profile_id,
            status=status,
            payload_json=payload_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def update_run_counts(
        self,
        run: MatchingRun,
        *,
        candidate_pool_count: int,
        hard_filtered_count: int,
        shortlisted_count: int,
        status: str = "completed",
        payload_json: Optional[dict] = None,
    ) -> MatchingRun:
        run.candidate_pool_count = candidate_pool_count
        run.hard_filtered_count = hard_filtered_count
        run.shortlisted_count = shortlisted_count
        run.status = status
        if payload_json is not None:
            run.payload_json = payload_json
        self.session.flush()
        return run

    def create_match(
        self,
        *,
        matching_run_id,
        vacancy_id,
        vacancy_version_id,
        candidate_profile_id,
        candidate_profile_version_id,
        status: str,
        hard_filter_passed: bool,
        filter_reason_codes_json: list,
        embedding_score=None,
        deterministic_score=None,
        llm_rank_score=None,
        llm_rank_position=None,
        rationale_json: Optional[dict] = None,
    ) -> Match:
        row = Match(
            matching_run_id=matching_run_id,
            vacancy_id=vacancy_id,
            vacancy_version_id=vacancy_version_id,
            candidate_profile_id=candidate_profile_id,
            candidate_profile_version_id=candidate_profile_version_id,
            status=status,
            hard_filter_passed=hard_filter_passed,
            filter_reason_codes_json=filter_reason_codes_json,
            embedding_score=embedding_score,
            deterministic_score=deterministic_score,
            llm_rank_score=llm_rank_score,
            llm_rank_position=llm_rank_position,
            rationale_json=rationale_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def get_matches_for_run(self, matching_run_id) -> list[Match]:
        stmt = select(Match).where(Match.matching_run_id == matching_run_id)
        return list(self.session.execute(stmt).scalars().all())
