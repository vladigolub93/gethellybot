from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.matching.service import MatchingService
from src.matching.waves import InviteWaveService


class MatchingProcessingService:
    def __init__(self, session):
        self.session = session
        self.queue = DatabaseQueueClient(session)
        self.vacancies = VacanciesRepository(session)
        self.matching = MatchingRepository(session)
        self.notifications = NotificationsRepository(session)
        self.matching_service = MatchingService(session)
        self.wave_service = InviteWaveService(session)

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
        return {
            "candidate_profile_id": candidate_profile_id,
            "open_vacancies_count": len(open_vacancies),
        }

    def _process_vacancy_run(self, job) -> dict:
        payload = job.payload_json or {}
        result = self.matching_service.execute_for_vacancy(
            vacancy_id=payload["vacancy_id"],
            trigger_type=payload.get("trigger_type", "vacancy_open"),
            trigger_candidate_profile_id=payload.get("trigger_candidate_profile_id"),
        )
        if result["shortlisted_count"] > 0:
            self.queue.enqueue(
                JobMessage(
                    job_type="interview_dispatch_invites_v1",
                    payload={
                        "vacancy_id": result["vacancy_id"],
                        "matching_run_id": result["matching_run_id"],
                        "limit": 3,
                    },
                    idempotency_key=f"interview_dispatch_invites_v1:{result['vacancy_id']}:{result['matching_run_id']}",
                    entity_type="vacancy",
                    entity_id=payload["vacancy_id"],
                )
            )
        if payload.get("trigger_type") == "manager_manual_request":
            self._notify_manager_manual_refresh_result(
                vacancy_id=payload["vacancy_id"],
                shortlisted_count=result["shortlisted_count"],
            )
        return result

    def _notify_manager_manual_refresh_result(self, *, vacancy_id, shortlisted_count: int) -> None:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        manager_user_id = getattr(vacancy, "manager_user_id", None)
        if vacancy is None or manager_user_id is None:
            return

        if shortlisted_count > 0:
            invited_now = min(shortlisted_count, 3)
            text = (
                f"Matching refresh complete. I found {shortlisted_count} strong "
                f"{self._pluralize_candidates(shortlisted_count)} for this vacancy and started "
                f"inviting the top {invited_now} to the AI interview. "
                "I'll send you candidate profiles here once they complete it."
            )
        else:
            active_match_count = len(self.matching.list_active_for_vacancy(vacancy.id))
            if active_match_count > 0:
                verb = "is" if active_match_count == 1 else "are"
                text = (
                    "Matching refresh complete. I didn't find new strong candidates right now, "
                    f"but there {verb} {active_match_count} "
                    f"{self._pluralize_candidates(active_match_count)} already in progress "
                    "for this vacancy. I'll send profiles here once the interview and evaluation are done."
                )
            else:
                text = (
                    "Matching refresh complete. I didn't find any strong candidates for this vacancy yet. "
                    "I'll keep looking and send profiles here once someone passes the interview "
                    "and evaluation."
                )

        self.notifications.create(
            user_id=manager_user_id,
            entity_type="vacancy",
            entity_id=vacancy.id,
            template_key="vacancy_open",
            payload_json={"text": text},
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
