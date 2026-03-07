from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.db.models.candidates import CandidateProfileVersion
from src.db.models.interviews import InterviewAnswer
from src.db.models.vacancies import VacancyVersion
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.files import FilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.vacancies import VacanciesRepository


class CleanupService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.candidate_verifications = CandidateVerificationsRepository(session)
        self.files = FilesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matching = MatchingRepository(session)
        self.notifications = NotificationsRepository(session)
        self.vacancies = VacanciesRepository(session)

    def process_job(self, job) -> dict:
        payload = job.payload_json or {}
        if job.job_type == "cleanup_candidate_deletion_v1":
            return self._cleanup_candidate_profile(
                candidate_profile_id=self._coerce_uuid(payload["candidate_profile_id"])
            )
        if job.job_type == "cleanup_vacancy_deletion_v1":
            return self._cleanup_vacancy(
                vacancy_id=self._coerce_uuid(payload["vacancy_id"])
            )
        raise ValueError(f"Unsupported cleanup job type: {job.job_type}")

    def _cleanup_candidate_profile(self, *, candidate_profile_id) -> dict:
        profile = self.candidates.get_by_id(candidate_profile_id)
        if profile is None:
            raise ValueError("Candidate profile not found for cleanup.")

        matches = self.matching.list_all_for_candidate(profile.id)
        sessions = self.interviews.list_for_candidate_profile(profile.id)
        cancelled_notifications = self.notifications.cancel_for_entities(
            refs=(
                [("candidate_profile", profile.id)]
                + [("match", match.id) for match in matches]
                + [("interview_session", session.id) for session in sessions]
            ),
            exclude_template_keys=["candidate_deleted"],
        )
        deleted_files = self._mark_deleted_files(
            file_ids=self._candidate_file_ids(profile.id, session_ids=[session.id for session in sessions]),
            reason="candidate_profile_deleted",
        )
        return {
            "status": "completed",
            "candidate_profile_id": str(profile.id),
            "cancelled_notifications": cancelled_notifications,
            "deleted_files": deleted_files,
        }

    def _cleanup_vacancy(self, *, vacancy_id) -> dict:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        if vacancy is None:
            raise ValueError("Vacancy not found for cleanup.")

        matches = self.matching.list_all_for_vacancy(vacancy.id)
        sessions = self.interviews.list_for_vacancy(vacancy.id)
        cancelled_notifications = self.notifications.cancel_for_entities(
            refs=(
                [("vacancy", vacancy.id)]
                + [("match", match.id) for match in matches]
                + [("interview_session", session.id) for session in sessions]
            ),
            exclude_template_keys=["vacancy_deleted"],
        )
        deleted_files = self._mark_deleted_files(
            file_ids=self._vacancy_file_ids(vacancy.id, session_ids=[session.id for session in sessions]),
            reason="vacancy_deleted",
        )
        return {
            "status": "completed",
            "vacancy_id": str(vacancy.id),
            "cancelled_notifications": cancelled_notifications,
            "deleted_files": deleted_files,
        }

    def _candidate_file_ids(self, profile_id, *, session_ids: list) -> list:
        file_ids = set()
        stmt = select(CandidateProfileVersion.source_file_id).where(
            CandidateProfileVersion.profile_id == profile_id,
            CandidateProfileVersion.source_file_id.is_not(None),
        )
        file_ids.update(file_id for file_id in self.session.execute(stmt).scalars().all() if file_id is not None)

        for verification in self.candidate_verifications.list_for_profile(profile_id):
            if verification.video_file_id is not None:
                file_ids.add(verification.video_file_id)

        file_ids.update(self._interview_answer_file_ids(session_ids))
        return list(file_ids)

    def _vacancy_file_ids(self, vacancy_id, *, session_ids: list) -> list:
        file_ids = set()
        stmt = select(VacancyVersion.source_file_id).where(
            VacancyVersion.vacancy_id == vacancy_id,
            VacancyVersion.source_file_id.is_not(None),
        )
        file_ids.update(file_id for file_id in self.session.execute(stmt).scalars().all() if file_id is not None)
        file_ids.update(self._interview_answer_file_ids(session_ids))
        return list(file_ids)

    def _interview_answer_file_ids(self, session_ids: list) -> set:
        if not session_ids:
            return set()
        stmt = select(InterviewAnswer.file_id).where(
            InterviewAnswer.session_id.in_(session_ids),
            InterviewAnswer.file_id.is_not(None),
        )
        return {file_id for file_id in self.session.execute(stmt).scalars().all() if file_id is not None}

    def _mark_deleted_files(self, *, file_ids: list, reason: str) -> int:
        deleted = 0
        for file_id in file_ids:
            file_row = self.files.get_by_id(file_id)
            if file_row is None or file_row.deleted_at is not None:
                continue
            self.files.mark_deleted(file_row, reason=reason)
            deleted += 1
        return deleted

    def _coerce_uuid(self, value):
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
