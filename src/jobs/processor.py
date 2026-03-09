from src.candidate_profile.processing import CandidateProcessingService
from src.cleanup.service import CleanupService
from src.evaluation.service import EvaluationService
from src.interview.processing import InterviewProcessingService
from src.matching.processing import MatchingProcessingService
from src.notifications.delivery import NotificationDeliveryService
from src.storage.service import FileStorageService
from src.vacancy.processing import VacancyProcessingService


def process_job(session, job):
    if job.job_type.startswith("candidate_"):
        return CandidateProcessingService(session).process_job(job)
    if job.job_type.startswith("cleanup_"):
        return CleanupService(session).process_job(job)
    if job.job_type.startswith("evaluation_"):
        payload = job.payload_json or {}
        return EvaluationService(session).evaluate_interview(
            interview_session_id=payload["interview_session_id"],
        )
    if job.job_type.startswith("interview_"):
        return InterviewProcessingService(session).process_job(job)
    if job.job_type.startswith("matching_"):
        return MatchingProcessingService(session).process_job(job)
    if job.job_type.startswith("notification_"):
        return NotificationDeliveryService(session).process_job(job)
    if job.job_type.startswith("file_"):
        return FileStorageService(session).process_job(job)
    if job.job_type.startswith("vacancy_"):
        return VacancyProcessingService(session).process_job(job)
    raise ValueError(f"Unsupported job type: {job.job_type}")
