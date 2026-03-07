from __future__ import annotations

from dataclasses import dataclass

from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage


@dataclass(frozen=True)
class WavePolicy:
    target_completed_interviews: int = 2
    default_wave_size: int = 3
    expansion_wave_size: int = 2


class InviteWaveService:
    def __init__(self, session, *, policy: WavePolicy | None = None):
        self.session = session
        self.policy = policy or WavePolicy()
        self.matching = MatchingRepository(session)
        self.interviews = InterviewsRepository(session)
        self.queue = DatabaseQueueClient(session)

    def evaluate_wave(self, *, wave_id) -> dict:
        wave = self.matching.get_wave_by_id(wave_id)
        if wave is None:
            raise ValueError("Invite wave not found.")

        payload = dict(wave.payload_json or {})
        invited_match_ids = payload.get("invited_match_ids") or []
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
                "completed_interviews_count": completed_count,
                "target_completed_interviews": self.policy.target_completed_interviews,
                "remaining_shortlisted_count": remaining_shortlisted_count,
                "shortlist_exhausted": shortlist_exhausted,
            },
        )

        expansion_enqueued = False
        if completed_count < self.policy.target_completed_interviews and not shortlist_exhausted:
            self.queue.enqueue(
                JobMessage(
                    job_type="interview_dispatch_invites_v1",
                    payload={
                        "vacancy_id": str(wave.vacancy_id),
                        "matching_run_id": str(wave.matching_run_id),
                        "limit": self.policy.expansion_wave_size,
                    },
                    idempotency_key=f"interview_dispatch_invites_v1:{wave.vacancy_id}:{wave.matching_run_id}:wave:{wave.wave_no + 1}",
                    entity_type="invite_wave",
                    entity_id=wave.id,
                )
            )
            expansion_enqueued = True

        return {
            "invite_wave_id": str(wave.id),
            "vacancy_id": str(wave.vacancy_id),
            "matching_run_id": str(wave.matching_run_id),
            "wave_no": wave.wave_no,
            "completed_interviews_count": completed_count,
            "target_completed_interviews": self.policy.target_completed_interviews,
            "remaining_shortlisted_count": remaining_shortlisted_count,
            "shortlist_exhausted": shortlist_exhausted,
            "expansion_enqueued": expansion_enqueued,
        }
