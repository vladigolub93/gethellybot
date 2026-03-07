from src.db.repositories.vacancies import VacanciesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.matching.service import MatchingService


class MatchingProcessingService:
    def __init__(self, session):
        self.session = session
        self.queue = DatabaseQueueClient(session)
        self.vacancies = VacanciesRepository(session)
        self.matching_service = MatchingService(session)

    def process_job(self, job) -> dict:
        if job.job_type == "matching_candidate_ready_v1":
            return self._process_candidate_ready(job)
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
        return self.matching_service.execute_for_vacancy(
            vacancy_id=payload["vacancy_id"],
            trigger_type=payload.get("trigger_type", "vacancy_open"),
            trigger_candidate_profile_id=payload.get("trigger_candidate_profile_id"),
        )
