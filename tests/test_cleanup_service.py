from types import SimpleNamespace
from uuid import uuid4

from src.cleanup.service import CleanupService


class FakeSession:
    def execute(self, _stmt):
        raise AssertionError("Direct SQL execution should be monkeypatched in this test.")


class FakeCandidateProfilesRepository:
    def __init__(self, profile):
        self.profile = profile

    def get_by_id(self, profile_id):
        return self.profile if self.profile.id == profile_id else None


class FakeVacanciesRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_by_id(self, vacancy_id):
        return self.vacancy if self.vacancy.id == vacancy_id else None


class FakeMatchingRepository:
    def __init__(self, matches):
        self.matches = matches

    def list_all_for_candidate(self, candidate_profile_id):
        return [match for match in self.matches if getattr(match, "candidate_profile_id", None) == candidate_profile_id]

    def list_all_for_vacancy(self, vacancy_id):
        return [match for match in self.matches if getattr(match, "vacancy_id", None) == vacancy_id]


class FakeInterviewsRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def list_for_candidate_profile(self, candidate_profile_id):
        return [row for row in self.sessions if getattr(row, "candidate_profile_id", None) == candidate_profile_id]

    def list_for_vacancy(self, vacancy_id):
        return [row for row in self.sessions if getattr(row, "vacancy_id", None) == vacancy_id]


class FakeNotificationsRepository:
    def __init__(self):
        self.calls = []

    def cancel_for_entities(self, *, refs, exclude_template_keys=None):
        self.calls.append({"refs": refs, "exclude_template_keys": exclude_template_keys})
        return 3


class FakeFilesRepository:
    def __init__(self, rows):
        self.rows = {row.id: row for row in rows}

    def get_by_id(self, file_id):
        return self.rows.get(file_id)

    def mark_deleted(self, file_row, *, reason):
        file_row.status = "deleted"
        file_row.deleted_at = "now"
        file_row.reason = reason
        return file_row


class FakeCandidateVerificationsRepository:
    pass


def test_candidate_cleanup_cancels_related_notifications_and_deletes_files(monkeypatch) -> None:
    profile = SimpleNamespace(id=uuid4())
    match = SimpleNamespace(id=uuid4(), candidate_profile_id=profile.id)
    session = SimpleNamespace(id=uuid4(), candidate_profile_id=profile.id)
    file_a = SimpleNamespace(id=uuid4(), deleted_at=None, status="stored")
    file_b = SimpleNamespace(id=uuid4(), deleted_at=None, status="stored")

    service = CleanupService(FakeSession())
    service.candidates = FakeCandidateProfilesRepository(profile)
    service.matching = FakeMatchingRepository([match])
    service.interviews = FakeInterviewsRepository([session])
    service.notifications = FakeNotificationsRepository()
    service.files = FakeFilesRepository([file_a, file_b])
    service.candidate_verifications = FakeCandidateVerificationsRepository()
    monkeypatch.setattr(service, "_candidate_file_ids", lambda profile_id, session_ids: [file_a.id, file_b.id])

    result = service.process_job(
        SimpleNamespace(
            job_type="cleanup_candidate_deletion_v1",
            payload_json={"candidate_profile_id": str(profile.id)},
        )
    )

    assert result["status"] == "completed"
    assert result["cancelled_notifications"] == 3
    assert result["deleted_files"] == 2
    assert service.notifications.calls[0]["exclude_template_keys"] == ["candidate_deleted"]
    assert file_a.status == "deleted"
    assert file_b.status == "deleted"


def test_vacancy_cleanup_cancels_related_notifications_and_deletes_files(monkeypatch) -> None:
    vacancy = SimpleNamespace(id=uuid4())
    match = SimpleNamespace(id=uuid4(), vacancy_id=vacancy.id)
    session = SimpleNamespace(id=uuid4(), vacancy_id=vacancy.id)
    file_row = SimpleNamespace(id=uuid4(), deleted_at=None, status="stored")

    service = CleanupService(FakeSession())
    service.vacancies = FakeVacanciesRepository(vacancy)
    service.matching = FakeMatchingRepository([match])
    service.interviews = FakeInterviewsRepository([session])
    service.notifications = FakeNotificationsRepository()
    service.files = FakeFilesRepository([file_row])
    monkeypatch.setattr(service, "_vacancy_file_ids", lambda vacancy_id, session_ids: [file_row.id])

    result = service.process_job(
        SimpleNamespace(
            job_type="cleanup_vacancy_deletion_v1",
            payload_json={"vacancy_id": str(vacancy.id)},
        )
    )

    assert result["status"] == "completed"
    assert result["cancelled_notifications"] == 3
    assert result["deleted_files"] == 1
    assert service.notifications.calls[0]["exclude_template_keys"] == ["vacancy_deleted"]
    assert file_row.status == "deleted"
