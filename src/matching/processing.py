from __future__ import annotations
from uuid import UUID

from src.cv_challenge.service import CandidateCvChallengeService
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.matching.policy import MATCH_BATCH_SIZE, MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY
from src.matching.review import MatchingReviewService
from src.matching.service import MatchingService
from src.matching.waves import InviteWaveService
from src.telegram.keyboards import candidate_cv_challenge_keyboard


class MatchingProcessingService:
    def __init__(self, session):
        self.session = session
        self.queue = DatabaseQueueClient(session)
        self.candidate_profiles = CandidateProfilesRepository(session)
        self.job_logs = JobExecutionLogsRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.matching = MatchingRepository(session)
        self.notifications = NotificationsRepository(session)
        self.matching_service = MatchingService(session)
        self.review_service = MatchingReviewService(session)
        self.wave_service = InviteWaveService(session)
        self.cv_challenge = CandidateCvChallengeService(session)

    def process_job(self, job) -> dict:
        if job.job_type == "matching_candidate_ready_v1":
            return self._process_candidate_ready(job)
        if job.job_type == "matching_send_invite_wave_reminder_v1":
            return self._process_invite_wave_reminder(job)
        if job.job_type == "matching_evaluate_invite_wave_v1":
            return self._process_invite_wave_evaluation(job)
        if job.job_type == "matching_run_for_vacancy_v1":
            return self._process_vacancy_run(job)
        raise ValueError(f"Unsupported matching job type: {job.job_type}")

    def _process_candidate_ready(self, job) -> dict:
        payload = job.payload_json or {}
        candidate_profile_id = payload.get("candidate_profile_id")
        open_vacancies = self.vacancies.get_open_vacancies()
        for vacancy in open_vacancies:
            self.queue.enqueue(
                JobMessage(
                    job_type="matching_run_for_vacancy_v1",
                    payload={
                        "vacancy_id": str(vacancy.id),
                        "trigger_type": "candidate_ready",
                        "trigger_candidate_profile_id": candidate_profile_id,
                    },
                    idempotency_key=f"matching_run_for_vacancy_v1:{vacancy.id}:candidate:{candidate_profile_id}",
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                )
            )
        if not open_vacancies and candidate_profile_id:
            self._notify_candidate_waiting_game(candidate_profile_id)
        return {
            "candidate_profile_id": candidate_profile_id,
            "open_vacancies_count": len(open_vacancies),
        }

    def _notify_candidate_waiting_game(self, candidate_profile_id: str) -> None:
        try:
            profile_id = UUID(str(candidate_profile_id))
        except (TypeError, ValueError):
            return
        profile = self.candidate_profiles.get_by_id(profile_id)
        if profile is None:
            return
        invitation = self.cv_challenge.build_invitation_payload(profile.user_id)
        if invitation is None:
            return
        self.notifications.create(
            user_id=profile.user_id,
            entity_type=invitation["entityType"],
            entity_id=profile.id,
            template_key="candidate_ready",
            payload_json={
                "text": invitation["text"],
                "reply_markup": candidate_cv_challenge_keyboard(invitation["launchUrl"]),
            },
        )

    def _process_vacancy_run(self, job) -> dict:
        payload = job.payload_json or {}
        result = self.matching_service.execute_for_vacancy(
            vacancy_id=payload["vacancy_id"],
            trigger_type=payload.get("trigger_type", "vacancy_open"),
            trigger_candidate_profile_id=payload.get("trigger_candidate_profile_id"),
        )
        trigger_type = payload.get("trigger_type", "vacancy_open")
        manager_review_triggers = {"vacancy_open", "manager_manual_request"}
        candidate_review_triggers = {"candidate_ready", "candidate_manual_request"}
        review_dispatch_result = None
        if result["shortlisted_count"] > 0 and trigger_type in manager_review_triggers:
            review_dispatch_result = self.review_service.dispatch_manager_batch_for_vacancy(
                vacancy_id=result["vacancy_id"],
                force=trigger_type == "manager_manual_request",
                trigger_type="job",
            )
        elif result["shortlisted_count"] > 0 and trigger_type in candidate_review_triggers:
            self.review_service.dispatch_candidate_batch_for_profile(
                candidate_profile_id=payload.get("trigger_candidate_profile_id"),
                force=trigger_type == "candidate_manual_request",
                trigger_type="job",
            )
        elif result["shortlisted_count"] > 0:
            review_dispatch_result = self.review_service.dispatch_manager_batch_for_vacancy(
                vacancy_id=result["vacancy_id"],
                force=False,
                trigger_type="job",
            )
        if trigger_type == "manager_manual_request":
            self._notify_manager_manual_refresh_result(
                vacancy_id=payload["vacancy_id"],
                shortlisted_count=result["shortlisted_count"],
                review_dispatch_result=review_dispatch_result,
            )
        if trigger_type == "candidate_manual_request":
            self._maybe_notify_candidate_manual_refresh_result(
                job=job,
                candidate_profile_id=payload.get("trigger_candidate_profile_id"),
                request_id=payload.get("candidate_manual_request_id"),
                shortlisted_count=result["shortlisted_count"],
            )
        return result

    def _maybe_notify_candidate_manual_refresh_result(
        self,
        *,
        job,
        candidate_profile_id: str | None,
        request_id: str | None,
        shortlisted_count: int,
    ) -> None:
        if not candidate_profile_id or not request_id:
            return

        related_jobs = self.job_logs.list_candidate_manual_request_jobs(
            candidate_profile_id=str(candidate_profile_id),
            request_id=str(request_id),
        )
        current_job_id = str(getattr(job, "id", ""))
        if any(
            str(getattr(row, "id", "")) != current_job_id and getattr(row, "status", None) in {"queued", "running"}
            for row in related_jobs
        ):
            return

        total_shortlisted = max(int(shortlisted_count or 0), 0)
        had_failed_jobs = False
        for related_job in related_jobs:
            if str(getattr(related_job, "id", "")) == current_job_id:
                continue
            if getattr(related_job, "status", None) == "completed":
                total_shortlisted += max(int((getattr(related_job, "result_json", None) or {}).get("shortlisted_count") or 0), 0)
            elif getattr(related_job, "status", None) == "failed":
                had_failed_jobs = True

        if total_shortlisted > 0:
            return

        self._notify_candidate_manual_refresh_result(
            candidate_profile_id=str(candidate_profile_id),
            had_failed_jobs=had_failed_jobs,
        )

    def _notify_manager_manual_refresh_result(
        self,
        *,
        vacancy_id,
        shortlisted_count: int,
        review_dispatch_result: dict | None = None,
    ) -> None:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        manager_user_id = getattr(vacancy, "manager_user_id", None)
        if vacancy is None or manager_user_id is None:
            return

        if review_dispatch_result and review_dispatch_result.get("status") == "vacancy_cap_reached":
            text = (
                "Matching refresh complete. I found strong candidates for this vacancy, "
                f"but you already have {MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY} candidates in the active interview pipeline. "
                "Wait until one finishes or drops out before I send more profiles."
            )
        elif shortlisted_count > 0:
            text = (
                f"Matching refresh complete. I found {shortlisted_count} strong "
                f"{self._pluralize_candidates(shortlisted_count)} for this vacancy and sent you "
                f"the first batch of up to {MATCH_BATCH_SIZE} for pre-interview review."
            )
        else:
            active_match_count = len(self.matching.list_active_for_vacancy(vacancy.id))
            if active_match_count > 0:
                verb = "is" if active_match_count == 1 else "are"
                text = (
                    "Matching refresh complete. I didn't find new strong candidates right now, "
                    f"but there {verb} {active_match_count} "
                    f"{self._pluralize_candidates(active_match_count)} already active in the current review pipeline "
                    "for this vacancy. I'll send the next candidates as soon as this queue moves."
                )
            else:
                text = (
                    "Matching refresh complete. I didn't find any strong candidates for this vacancy yet. "
                    "I'll keep looking and send strong profiles here as soon as matching finds them."
                )

        self.notifications.create(
            user_id=manager_user_id,
            entity_type="vacancy",
            entity_id=vacancy.id,
            template_key="vacancy_open",
            payload_json={"text": text},
            allow_duplicate=True,
        )

    def _notify_candidate_manual_refresh_result(
        self,
        *,
        candidate_profile_id: str,
        had_failed_jobs: bool,
    ) -> None:
        try:
            profile_id = UUID(str(candidate_profile_id))
        except (TypeError, ValueError):
            return

        profile = self.candidate_profiles.get_by_id(profile_id)
        if profile is None:
            return

        active_match_count = len(self.matching.list_active_for_candidate(profile.id))
        challenge_payload = self.cv_challenge.build_invitation_payload(profile.user_id)

        if had_failed_jobs:
            text = (
                "I rechecked current open roles for your profile, but I couldn't complete every search cleanly just now. "
                "Nothing new is ready yet."
            )
        elif active_match_count > 0:
            verb = "is" if active_match_count == 1 else "are"
            noun = "opportunity" if active_match_count == 1 else "opportunities"
            text = (
                "I checked current open roles again. I didn't find any new matches for you right now, "
                f"but there {verb} already {active_match_count} active {noun} in progress."
            )
        else:
            text = (
                "I checked current open roles again. I didn't find any new matches for your profile right now."
            )

        if challenge_payload is not None:
            text += " While you wait, you can open Helly CV Challenge and play a quick round."
        else:
            text += " I'll keep watching and message you as soon as something strong appears."

        self.notifications.create(
            user_id=profile.user_id,
            entity_type="candidate_profile",
            entity_id=profile.id,
            template_key="candidate_ready",
            payload_json={
                "text": text,
                "reply_markup": (
                    candidate_cv_challenge_keyboard(challenge_payload["launchUrl"])
                    if challenge_payload is not None
                    else None
                ),
            },
            allow_duplicate=True,
        )

    @staticmethod
    def _pluralize_candidates(count: int) -> str:
        return "candidate" if count == 1 else "candidates"

    def _process_invite_wave_evaluation(self, job) -> dict:
        payload = job.payload_json or {}
        return self.wave_service.evaluate_wave(wave_id=payload["invite_wave_id"])

    def _process_invite_wave_reminder(self, job) -> dict:
        payload = job.payload_json or {}
        return self.wave_service.send_wave_reminders(wave_id=payload["invite_wave_id"])
