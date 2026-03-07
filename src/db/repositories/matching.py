from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.matching import InviteWave, Match, MatchingRun


class MatchingRepository:
    ACTIVE_MATCH_STATUSES = (
        "shortlisted",
        "invited",
        "accepted",
        "interview_completed",
        "manager_review",
    )

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

    def get_run_by_id(self, matching_run_id) -> Optional[MatchingRun]:
        stmt = select(MatchingRun).where(MatchingRun.id == matching_run_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_run_for_vacancy(self, vacancy_id, *, status: Optional[str] = None) -> Optional[MatchingRun]:
        stmt = select(MatchingRun).where(MatchingRun.vacancy_id == vacancy_id)
        if status is not None:
            stmt = stmt.where(MatchingRun.status == status)
        stmt = stmt.order_by(MatchingRun.created_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_shortlisted_for_vacancy(self, vacancy_id, *, limit: int = 3) -> list[Match]:
        stmt = (
            select(Match)
            .where(
                Match.vacancy_id == vacancy_id,
                Match.status == "shortlisted",
            )
            .order_by(Match.llm_rank_position.asc().nulls_last(), Match.deterministic_score.desc().nulls_last())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def count_shortlisted_for_vacancy(self, vacancy_id) -> int:
        stmt = select(Match).where(
            Match.vacancy_id == vacancy_id,
            Match.status == "shortlisted",
        )
        return len(list(self.session.execute(stmt).scalars().all()))

    def get_next_wave_no(self, matching_run_id) -> int:
        stmt = select(InviteWave).where(InviteWave.matching_run_id == matching_run_id)
        waves = list(self.session.execute(stmt).scalars().all())
        if not waves:
            return 1
        return max(wave.wave_no for wave in waves) + 1

    def create_invite_wave(
        self,
        *,
        vacancy_id,
        matching_run_id,
        wave_no: int,
        status: str = "created",
        invited_count: int = 0,
        completed_interviews_count: int = 0,
        target_invites_count: int = 0,
        payload_json: Optional[dict] = None,
    ) -> InviteWave:
        row = InviteWave(
            vacancy_id=vacancy_id,
            matching_run_id=matching_run_id,
            wave_no=wave_no,
            status=status,
            invited_count=invited_count,
            completed_interviews_count=completed_interviews_count,
            target_invites_count=target_invites_count,
            payload_json=payload_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def complete_invite_wave(
        self,
        wave: InviteWave,
        *,
        invited_count: int,
        completed_interviews_count: int = 0,
        status: str = "completed",
        payload_json: Optional[dict] = None,
    ) -> InviteWave:
        wave.invited_count = invited_count
        wave.completed_interviews_count = completed_interviews_count
        wave.status = status
        if payload_json is not None:
            wave.payload_json = payload_json
        self.session.flush()
        return wave

    def list_active_invite_waves(self, *, limit: int = 20) -> list[InviteWave]:
        stmt = (
            select(InviteWave)
            .where(InviteWave.status.in_(("created", "running")))
            .order_by(InviteWave.created_at.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    @staticmethod
    def _parse_payload_dt(value) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def list_due_invite_wave_reminders(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[InviteWave]:
        now = now or datetime.now(timezone.utc)
        rows = []
        for wave in self.list_active_invite_waves(limit=limit * 4):
            payload = wave.payload_json or {}
            reminder_due_at = self._parse_payload_dt(payload.get("reminder_due_at"))
            reminder_sent_at = self._parse_payload_dt(payload.get("reminder_sent_at"))
            if reminder_due_at and reminder_due_at <= now and reminder_sent_at is None:
                rows.append(wave)
            if len(rows) >= limit:
                break
        return rows

    def list_due_invite_wave_evaluations(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[InviteWave]:
        now = now or datetime.now(timezone.utc)
        rows = []
        for wave in self.list_active_invite_waves(limit=limit * 4):
            payload = wave.payload_json or {}
            expires_at = self._parse_payload_dt(payload.get("expires_at"))
            evaluated_at = self._parse_payload_dt(payload.get("evaluated_at"))
            if expires_at and expires_at <= now and evaluated_at is None:
                rows.append(wave)
            if len(rows) >= limit:
                break
        return rows

    def get_wave_by_id(self, wave_id) -> Optional[InviteWave]:
        stmt = select(InviteWave).where(InviteWave.id == wave_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, match_id) -> Optional[Match]:
        stmt = select(Match).where(Match.id == match_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_ids(self, match_ids: list) -> list[Match]:
        if not match_ids:
            return []
        stmt = select(Match).where(Match.id.in_(match_ids))
        return list(self.session.execute(stmt).scalars().all())

    def get_latest_invited_for_candidate(self, candidate_profile_id) -> Optional[Match]:
        stmt = (
            select(Match)
            .where(
                Match.candidate_profile_id == candidate_profile_id,
                Match.status == "invited",
            )
            .order_by(Match.updated_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_active_for_candidate(self, candidate_profile_id) -> list[Match]:
        stmt = select(Match).where(
            Match.candidate_profile_id == candidate_profile_id,
            Match.status.in_(self.ACTIVE_MATCH_STATUSES),
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_all_for_candidate(self, candidate_profile_id) -> list[Match]:
        stmt = select(Match).where(Match.candidate_profile_id == candidate_profile_id)
        return list(self.session.execute(stmt).scalars().all())

    def list_active_for_vacancy(self, vacancy_id) -> list[Match]:
        stmt = select(Match).where(
            Match.vacancy_id == vacancy_id,
            Match.status.in_(self.ACTIVE_MATCH_STATUSES),
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_all_for_vacancy(self, vacancy_id) -> list[Match]:
        stmt = select(Match).where(Match.vacancy_id == vacancy_id)
        return list(self.session.execute(stmt).scalars().all())

    def mark_invited(self, match: Match) -> Match:
        match.status = "invited"
        match.invitation_sent_at = datetime.now(timezone.utc)
        self.session.flush()
        return match

    def mark_candidate_responded(self, match: Match, *, status: str) -> Match:
        match.status = status
        match.candidate_response_at = datetime.now(timezone.utc)
        self.session.flush()
        return match

    def mark_invitation_expired(self, match: Match) -> Match:
        match.status = "expired"
        match.candidate_response_at = datetime.now(timezone.utc)
        self.session.flush()
        return match

    def mark_manager_decision(self, match: Match, *, status: str) -> Match:
        match.status = status
        match.manager_decision_at = datetime.now(timezone.utc)
        self.session.flush()
        return match

    def set_status(self, match: Match, *, status: str) -> Match:
        match.status = status
        self.session.flush()
        return match

    def mark_wave_reminder_sent(self, wave: InviteWave, *, payload_json: Optional[dict] = None) -> InviteWave:
        if payload_json is not None:
            wave.payload_json = payload_json
        self.session.flush()
        return wave

    def get_latest_manager_review_for_manager(self, vacancy_ids: list, *, manager_review_only: bool = True) -> Optional[Match]:
        if not vacancy_ids:
            return None
        stmt = select(Match).where(Match.vacancy_id.in_(vacancy_ids))
        if manager_review_only:
            stmt = stmt.where(Match.status == "manager_review")
        stmt = stmt.order_by(Match.updated_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()
