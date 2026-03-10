from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.messaging.service import MessagingService
from src.matching.policy import MATCH_BATCH_SIZE
from src.matching.review import MatchingReviewService


@dataclass(frozen=True)
class WavePolicy:
    target_completed_interviews: int = 2
    default_wave_size: int = MATCH_BATCH_SIZE
    expansion_wave_size: int = 2
    reminder_after_hours: int = 24
    expires_after_hours: int = 72


class InviteWaveService:
    def __init__(self, session, *, policy: WavePolicy | None = None):
        self.session = session
        self.policy = policy or WavePolicy()
        self.candidates = CandidateProfilesRepository(session)
        self.matching = MatchingRepository(session)
        self.interviews = InterviewsRepository(session)
        self.notifications = NotificationsRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.messaging = MessagingService(session)
        self.review_service = MatchingReviewService(session)

    def build_wave_timing_payload(self, *, matching_run_id, limit: int, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        return {
            "limit": limit,
            "matching_run_id": str(matching_run_id),
            "dispatched_at": now.isoformat(),
            "reminder_due_at": (now + timedelta(hours=self.policy.reminder_after_hours)).isoformat(),
            "expires_at": (now + timedelta(hours=self.policy.expires_after_hours)).isoformat(),
        }

    def send_wave_reminders(self, *, wave_id) -> dict:
        wave = self.matching.get_wave_by_id(wave_id)
        if wave is None:
            raise ValueError("Invite wave not found.")

        payload = dict(wave.payload_json or {})
        invited_match_ids = payload.get("invited_match_ids") or []
        matches = self.matching.list_by_ids(invited_match_ids)
        vacancy = self.vacancies.get_by_id(wave.vacancy_id)
        reminded_match_ids = []
        for match in matches:
            if getattr(match, "status", None) != "invited":
                continue
            candidate = self.candidates.get_by_id(match.candidate_profile_id)
            if candidate is None:
                continue
            self.notifications.create(
                user_id=candidate.user_id,
                entity_type="match",
                entity_id=match.id,
                template_key="candidate_interview_invitation_reminder",
                payload_json={
                    "text": self.messaging.compose(
                        f"Reminder: if you are interested in {getattr(vacancy, 'role_title', None) or 'this opportunity'}, "
                        "please reply with 'Accept interview' to continue or 'Skip opportunity' if you want to pass."
                    ),
                },
            )
            reminded_match_ids.append(str(match.id))

        self.matching.mark_wave_reminder_sent(
            wave,
            payload_json={
                **payload,
                "reminder_sent_at": datetime.now(timezone.utc).isoformat(),
                "reminded_match_ids": reminded_match_ids,
            },
        )

        return {
            "invite_wave_id": str(wave.id),
            "reminder_sent_count": len(reminded_match_ids),
            "reminded_match_ids": reminded_match_ids,
        }

    def evaluate_wave(self, *, wave_id) -> dict:
        wave = self.matching.get_wave_by_id(wave_id)
        if wave is None:
            raise ValueError("Invite wave not found.")

        payload = dict(wave.payload_json or {})
        invited_match_ids = payload.get("invited_match_ids") or []
        matches = self.matching.list_by_ids(invited_match_ids)
        expired_match_ids = []
        for match in matches:
            if getattr(match, "status", None) != "invited":
                continue
            self.matching.mark_invitation_expired(match)
            expired_match_ids.append(str(match.id))
        completed_count = self.interviews.count_completed_for_match_ids(invited_match_ids)
        remaining_shortlisted_count = self.matching.count_shortlisted_for_vacancy(wave.vacancy_id)
        shortlist_exhausted = remaining_shortlisted_count == 0

        self.matching.complete_invite_wave(
            wave,
            invited_count=wave.invited_count,
            completed_interviews_count=completed_count,
            status="completed",
            payload_json={
                **payload,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "completed_interviews_count": completed_count,
                "target_completed_interviews": self.policy.target_completed_interviews,
                "remaining_shortlisted_count": remaining_shortlisted_count,
                "shortlist_exhausted": shortlist_exhausted,
                "expired_match_ids": expired_match_ids,
            },
        )

        expansion_enqueued = False
        manager_review_dispatched = False
        if completed_count < self.policy.target_completed_interviews and not shortlist_exhausted:
            review_result = self.review_service.dispatch_manager_batch_for_vacancy(
                vacancy_id=wave.vacancy_id,
                force=True,
                trigger_type="job",
            )
            manager_review_dispatched = bool(review_result.get("notified")) or bool(review_result.get("batch_count"))

        return {
            "invite_wave_id": str(wave.id),
            "vacancy_id": str(wave.vacancy_id),
            "matching_run_id": str(wave.matching_run_id),
            "wave_no": wave.wave_no,
            "completed_interviews_count": completed_count,
            "target_completed_interviews": self.policy.target_completed_interviews,
            "remaining_shortlisted_count": remaining_shortlisted_count,
            "shortlist_exhausted": shortlist_exhausted,
            "expired_match_ids": expired_match_ids,
            "expansion_enqueued": expansion_enqueued,
            "manager_review_dispatched": manager_review_dispatched,
        }
