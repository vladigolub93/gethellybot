from types import SimpleNamespace
from uuid import uuid4

from src.candidate_profile.work_formats import build_work_formats_payload
from src.candidate_profile.service import CandidateProfileService
from src.candidate_profile.states import (
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_READY,
    CANDIDATE_STATE_SUMMARY_REVIEW,
    CANDIDATE_STATE_VERIFICATION_PENDING,
)


class FakeSession:
    def add(self, _obj):
        return None

    def flush(self):
        return None


class FakeCandidateProfilesRepository:
    def __init__(self):
        self.profile = None
        self.versions = []

    def get_active_by_user_id(self, _user_id):
        return self.profile

    def create(self, *, user_id, state):
        self.profile = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            state=state,
            current_version_id=None,
            work_formats_json=[],
            questions_context_json={},
            ready_at=None,
            deleted_at=None,
        )
        return self.profile

    def set_state(self, profile, state):
        profile.state = state
        return profile

    def next_version_no(self, _profile_id):
        return len(self.versions) + 1

    def create_version(self, **kwargs):
        version = SimpleNamespace(id=uuid4(), **kwargs)
        self.versions.append(version)
        return version

    def set_current_version(self, profile, version_id):
        profile.current_version_id = version_id
        return profile

    def update_questions_context(self, profile, questions_context_json):
        profile.questions_context_json = questions_context_json
        return profile

    def update_question_answers(self, profile, **kwargs):
        if "work_formats_json" in kwargs:
            normalized_payload = build_work_formats_payload(kwargs["work_formats_json"])
            kwargs["work_formats_json"] = normalized_payload.get("work_formats_json") or []
            kwargs["work_format"] = normalized_payload.get("work_format")
        elif "work_format" in kwargs and kwargs["work_format"] is not None:
            normalized_payload = build_work_formats_payload([kwargs["work_format"]])
            kwargs["work_formats_json"] = normalized_payload.get("work_formats_json") or []
            kwargs["work_format"] = normalized_payload.get("work_format")
        for key, value in kwargs.items():
            setattr(profile, key, value)
        return profile

    def mark_ready(self, profile):
        profile.ready_at = "now"
        return profile

    def soft_delete(self, profile):
        profile.deleted_at = "now"
        profile.state = "DELETED"
        return profile

    def get_current_version(self, profile):
        for version in self.versions:
            if version.id == profile.current_version_id:
                return version
        return None

    def mark_version_approved(self, version):
        version.approval_status = "approved"
        version.approved_by_user = True
        return version

    def count_versions_by_source_type(self, _profile_id, source_type):
        return len([version for version in self.versions if version.source_type == source_type])


class FakeStateService:
    def __init__(self):
        self.transitions = []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def transition(self, **kwargs):
        entity = kwargs["entity"]
        field = kwargs.get("state_field", "state")
        setattr(entity, field, kwargs["to_state"])
        self.transitions.append(kwargs)


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


class FakeMatchingRepository:
    def __init__(self):
        self.active_matches = []

    def list_active_for_candidate(self, candidate_profile_id):
        return [match for match in self.active_matches if match.candidate_profile_id == candidate_profile_id]


class FakeVacanciesRepository:
    def __init__(self):
        self.open_vacancies = []

    def get_open_vacancies(self):
        return list(self.open_vacancies)


class FakeInterviewsRepository:
    def __init__(self):
        self.sessions_by_match_id = {}

    def get_active_by_match_id(self, match_id):
        return self.sessions_by_match_id.get(match_id)


class FakeCandidateVerificationsRepository:
    def __init__(self):
        self.rows = []

    def get_pending_by_profile_id(self, profile_id):
        for row in reversed(self.rows):
            if row.profile_id == profile_id and row.status == "issued":
                return row
        return None

    def next_attempt_no(self, profile_id):
        return len([row for row in self.rows if row.profile_id == profile_id]) + 1

    def create(self, *, profile_id, attempt_no, phrase_text, status="issued"):
        row = SimpleNamespace(
            id=uuid4(),
            profile_id=profile_id,
            attempt_no=attempt_no,
            phrase_text=phrase_text,
            status=status,
            video_file_id=None,
            submitted_at=None,
        )
        self.rows.append(row)
        return row

    def mark_submitted(self, verification, *, video_file_id):
        verification.status = "submitted"
        verification.video_file_id = video_file_id
        verification.submitted_at = "now"
        return verification


def test_start_onboarding_moves_candidate_to_cv_pending() -> None:
    service = CandidateProfileService(FakeSession())
    service.repo = FakeCandidateProfilesRepository()
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = service.start_onboarding(user, trigger_ref_id=uuid4())

    assert profile.state == CANDIDATE_STATE_CV_PENDING


def test_handle_cv_intake_transitions_to_processing() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_CV_PENDING)

    result = service.handle_cv_intake(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Python backend engineer with 5 years experience",
    )

    assert result.status == "accepted"
    assert profile.state == CANDIDATE_STATE_CV_PROCESSING
    assert len(fake_repo.versions) == 1
    assert len(fake_queue.messages) == 1


def test_handle_cv_intake_rejects_meta_text_without_transition() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_CV_PENDING)

    result = service.handle_cv_intake(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Here is my CV",
    )

    assert result.status == "needs_more_detail"
    assert result.notification_template == "candidate_cv_needs_more_detail"
    assert profile.state == CANDIDATE_STATE_CV_PENDING
    assert len(fake_repo.versions) == 0
    assert len(fake_queue.messages) == 0


def test_approve_summary_moves_candidate_to_questions_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_summary",
    )

    assert result is not None
    assert result.status == "approved"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert version.approval_status == "approved"
    assert profile.questions_context_json["current_question_key"] == "salary"


def test_edit_summary_enqueues_processing_job() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="request_summary_change",
        structured_payload={"edit_text": "Please emphasize backend leadership and platform ownership."},
    )

    assert result is not None
    assert result.status == "accepted"
    assert profile.state == CANDIDATE_STATE_CV_PROCESSING
    assert len(fake_repo.versions) == 2
    assert fake_repo.versions[-1].source_type == "summary_user_edit"
    assert fake_repo.versions[-1].normalization_json["edit_request_text"] == "Please emphasize backend leadership and platform ownership."
    assert len(fake_queue.messages) == 1


def test_execute_summary_review_action_approve_moves_candidate_to_questions_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_summary",
    )

    assert result is not None
    assert result.status == "approved"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert version.approval_status == "approved"


def test_execute_deletion_action_confirm_soft_deletes_candidate_profile() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.interviews = FakeInterviewsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)
    match = SimpleNamespace(id=uuid4(), candidate_profile_id=profile.id, status="manager_review")
    interview = SimpleNamespace(id=uuid4(), match_id=match.id, state="IN_PROGRESS")
    service.matching.active_matches.append(match)
    service.interviews.sessions_by_match_id[match.id] = interview

    first = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_profile",
    )
    second = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
    )

    assert first is not None
    assert first.status == "confirmation_required"
    assert second is not None
    assert second.status == "deleted"
    assert profile.deleted_at == "now"
    assert profile.state == "DELETED"
    assert match.status == "cancelled"
    assert interview.state == "CANCELLED"


def test_summary_change_prompt_requests_specific_correction() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action=None,
        structured_payload={"needs_edit_details": True},
    )

    assert result is not None
    assert result.status == "awaiting_edit_details"
    assert profile.state == CANDIDATE_STATE_SUMMARY_REVIEW
    assert len(fake_queue.messages) == 0


def test_second_summary_edit_is_rejected() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    edited = fake_repo.create_version(
        profile_id=profile.id,
        version_no=2,
        source_type="summary_user_edit",
        summary_json={"headline": "Python backend engineer"},
    )
    fake_repo.set_current_version(profile, edited.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="request_summary_change",
        structured_payload={"edit_text": "Actually change it again"},
    )

    assert result is not None
    assert result.status == "limit_reached"
    assert profile.state == CANDIDATE_STATE_SUMMARY_REVIEW
    assert len(fake_queue.messages) == 0


def test_questions_answer_completion_moves_profile_to_verification_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Salary: $5000 per month. Location: Warsaw, Poland. Remote.",
    )

    assert result is not None
    assert result.status == "next_question"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert "remote" in result.notification_text.lower() or "office" in result.notification_text.lower()
    assert profile.salary_min == 5000
    assert profile.questions_context_json["current_question_key"] == "work_format"


def test_questions_answer_asks_next_question_in_sequence() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)
    fake_repo.update_questions_context(
        profile,
        {
            "follow_up_used": {"salary": False, "location": False, "work_format": False},
            "current_question_key": "salary",
        },
    )

    result = service.handle_questions_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "salary_min": 4500,
            "salary_currency": "USD",
            "salary_period": "month",
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert "remote" in result.notification_text.lower() or "office" in result.notification_text.lower()
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert profile.questions_context_json["current_question_key"] == "work_format"
    assert profile.salary_min == 4500


def test_questions_payload_filters_to_current_question_only() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)
    fake_repo.update_questions_context(
        profile,
        {
            "follow_up_used": {"salary": False, "location": False, "work_format": False},
            "current_question_key": "salary",
        },
    )

    result = service.handle_questions_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "salary_min": 4500,
            "salary_currency": "USD",
            "salary_period": "month",
            "location_text": "Kyiv, Ukraine",
            "city": "Kyiv",
            "country_code": "UA",
            "work_format": "remote",
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert "remote" in result.notification_text.lower() or "office" in result.notification_text.lower()
    assert profile.questions_context_json["current_question_key"] == "work_format"
    assert profile.salary_min == 4500
    assert getattr(profile, "location_text", None) is None
    assert getattr(profile, "work_format", None) is None


def test_questions_answer_requests_follow_up_when_partial() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="I'm in Warsaw, Poland.",
    )

    assert result is not None
    assert result.status == "incomplete"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert "salary" in result.notification_text.lower()
    assert getattr(profile, "location_text", None) is None


def test_parsed_questions_payload_completion_moves_profile_to_verification_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "salary_min": 5000,
            "salary_max": 5000,
            "salary_currency": "USD",
            "salary_period": "month",
            "location_text": "Warsaw, Poland",
            "city": "Warsaw",
            "country_code": "PL",
            "work_format": "remote",
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert profile.salary_min == 5000
    assert profile.questions_context_json["current_question_key"] == "work_format"


def test_questions_require_city_for_hybrid_or_office() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)
    fake_repo.update_question_answers(
        profile,
        salary_min=5000,
        salary_currency="USD",
        salary_period="month",
        work_format="hybrid",
    )

    result = service.handle_questions_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={"location_text": "Poland", "country_code": "PL"},
    )

    assert result is not None
    assert result.status == "follow_up"
    assert "city and country" in result.notification_text.lower()
    assert profile.questions_context_json["current_question_key"] == "location"


def test_questions_accept_all_formats_and_move_to_location() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)
    fake_repo.update_question_answers(
        profile,
        salary_min=5000,
        salary_currency="USD",
        salary_period="month",
    )
    fake_repo.update_questions_context(
        profile,
        {
            "follow_up_used": {"salary": False, "location": False, "work_format": False},
            "current_question_key": "work_format",
        },
    )

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="all formats",
    )

    assert result is not None
    assert result.status == "next_question"
    assert profile.work_formats_json == ["remote", "hybrid", "office"]
    assert getattr(profile, "work_format", None) is None
    assert profile.questions_context_json["current_question_key"] == "location"
    assert "city and country" in result.notification_text.lower()


def test_questions_complete_after_new_matching_preferences() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)
    fake_repo.update_question_answers(
        profile,
        salary_min=5000,
        salary_currency="USD",
        salary_period="month",
        work_format="remote",
        location_text="Warsaw, Poland",
        city="Warsaw",
        country_code="PL",
        english_level="B2",
        preferred_domains_json=["fintech", "saas"],
    )
    fake_repo.update_questions_context(
        profile,
        {
            "follow_up_used": {
                "salary": False,
                "work_format": False,
                "location": False,
                "english_level": False,
                "preferred_domains": False,
                "assessment_preferences": False,
            },
            "current_question_key": "assessment_preferences",
        },
    )

    result = service.handle_questions_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "show_take_home_task_roles": True,
            "show_live_coding_roles": False,
        },
    )

    assert result is not None
    assert result.status == "completed"
    assert profile.state == CANDIDATE_STATE_VERIFICATION_PENDING
    assert getattr(profile, "show_take_home_task_roles", None) is True
    assert getattr(profile, "show_live_coding_roles", None) is False


def test_questions_voice_answer_enqueues_processing_job() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="voice",
        file_id=uuid4(),
    )

    assert result is not None
    assert result.status == "queued"
    assert len(fake_queue.messages) == 1


def test_verification_submission_moves_candidate_to_ready() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_verifications = FakeCandidateVerificationsRepository()
    service.repo = fake_repo
    service.verifications = fake_verifications
    service.files = SimpleNamespace(get_by_id=lambda _file_id: SimpleNamespace(id=_file_id, kind="video"))
    service.state_service = fake_state
    service.queue = FakeQueue()

    class _FakeIngestion:
        def __init__(self, _session):
            return None

        def ingest_file(self, _file_row, *, prompt_text=None):
            assert prompt_text == "Helly check: sync complete"
            return SimpleNamespace(text="Helly check sync complete")

    import src.candidate_profile.service as candidate_service_module

    original_ingestion = candidate_service_module.ContentIngestionService
    candidate_service_module.ContentIngestionService = _FakeIngestion

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_VERIFICATION_PENDING)
    fake_verifications.create(
        profile_id=profile.id,
        attempt_no=1,
        phrase_text="Helly check: sync complete",
    )

    try:
        result = service.handle_verification_submission(
            user=user,
            raw_message_id=uuid4(),
            content_type="video",
            file_id=uuid4(),
        )
    finally:
        candidate_service_module.ContentIngestionService = original_ingestion

    assert result is not None
    assert result.status == "completed"
    assert profile.state == CANDIDATE_STATE_READY
    assert profile.ready_at == "now"
    assert len(service.queue.messages) == 1


def test_candidate_deletion_requires_confirmation_then_soft_deletes() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.verifications = FakeCandidateVerificationsRepository()
    service.matching = FakeMatchingRepository()
    service.interviews = FakeInterviewsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)
    match = SimpleNamespace(id=uuid4(), candidate_profile_id=profile.id, status="invited")
    interview = SimpleNamespace(id=uuid4(), match_id=match.id, state="IN_PROGRESS")
    service.matching.active_matches.append(match)
    service.interviews.sessions_by_match_id[match.id] = interview

    first = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_profile",
    )
    second = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
    )

    assert first is not None
    assert first.status == "confirmation_required"
    assert second is not None
    assert second.status == "deleted"
    assert profile.deleted_at == "now"
    assert profile.state == "DELETED"
    assert match.status == "cancelled"
    assert interview.state == "CANCELLED"
    assert len(service.queue.messages) == 1
    assert service.queue.messages[0].job_type == "cleanup_candidate_deletion_v1"


def test_execute_ready_action_enqueues_matching_for_open_vacancies() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)
    vacancy_a = SimpleNamespace(id=uuid4())
    vacancy_b = SimpleNamespace(id=uuid4())
    service.vacancies.open_vacancies = [vacancy_a, vacancy_b]

    result = service.execute_ready_action(
        user=user,
        raw_message_id="raw-ready-1",
        action="find_matching_vacancies",
    )

    assert result is not None
    assert result.status == "matching_requested"
    assert len(service.queue.messages) == 2
    assert service.queue.messages[0].job_type == "matching_run_for_vacancy_v1"
    assert service.queue.messages[0].payload["trigger_candidate_profile_id"] == str(profile.id)
    assert service.queue.messages[0].payload["trigger_type"] == "candidate_manual_request"
    assert service.queue.messages[0].payload["candidate_manual_request_id"] == "raw-ready-1"
    assert service.queue.messages[0].idempotency_key.endswith(":manual:raw-ready-1")
    assert service.queue.messages[1].job_type == "matching_run_for_vacancy_v1"


def test_execute_ready_action_handles_no_open_vacancies() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()
    service.queue = FakeQueue()
    service.cv_challenge = SimpleNamespace(
        build_invitation_payload=lambda user_id: {
            "launchUrl": "https://helly.test/webapp/cv-challenge",
        }
    )

    user = SimpleNamespace(id=uuid4())
    fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)

    result = service.execute_ready_action(
        user=user,
        raw_message_id="raw-ready-2",
        action="find_matching_vacancies",
    )

    assert result is not None
    assert result.status == "no_open_vacancies"
    assert service.queue.messages == []
    assert "helly cv challenge" in result.notification_text.lower()
    assert result.reply_markup["inline_keyboard"][0][0]["web_app"]["url"].endswith("/webapp/cv-challenge")


def test_execute_ready_action_updates_preferences_and_rechecks_matching() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)
    profile.salary_min = 4000
    profile.salary_max = 4500
    profile.salary_currency = "USD"
    profile.salary_period = "month"
    profile.location_text = "Kyiv, Ukraine"
    profile.country_code = "UA"
    profile.city = "Kyiv"
    profile.work_format = "remote"
    profile.english_level = "b1"
    profile.preferred_domains_json = ["fintech"]
    profile.show_take_home_task_roles = True
    profile.show_live_coding_roles = True
    vacancy_a = SimpleNamespace(id=uuid4())
    vacancy_b = SimpleNamespace(id=uuid4())
    service.vacancies.open_vacancies = [vacancy_a, vacancy_b]

    result = service.execute_ready_action(
        user=user,
        raw_message_id="raw-ready-update-1",
        action="update_matching_preferences",
        structured_payload={
            "salary_min": 5000,
            "salary_max": 5500,
            "work_format": "remote",
            "location_text": "Warsaw, Poland",
            "country_code": "PL",
            "city": "Warsaw",
            "english_level": "b2",
            "preferred_domains_json": ["saas"],
            "show_take_home_task_roles": False,
            "show_live_coding_roles": False,
        },
    )

    assert result is not None
    assert result.status == "preferences_updated_matching_requested"
    assert profile.salary_min == 5000
    assert profile.salary_max == 5500
    assert profile.location_text == "Warsaw, Poland"
    assert profile.country_code == "PL"
    assert profile.city == "Warsaw"
    assert profile.english_level == "b2"
    assert profile.preferred_domains_json == ["saas"]
    assert profile.show_take_home_task_roles is False
    assert profile.show_live_coding_roles is False
    assert "updated your" in result.notification_text.lower()
    assert "rechecking open roles" in result.notification_text.lower()
    assert len(service.queue.messages) == 2
    assert service.queue.messages[0].job_type == "matching_run_for_vacancy_v1"
    assert service.queue.messages[0].payload["trigger_candidate_profile_id"] == str(profile.id)


def test_execute_ready_action_requests_follow_up_for_hybrid_without_city() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)
    profile.salary_min = 4500
    profile.salary_max = 5000
    profile.salary_currency = "USD"
    profile.salary_period = "month"
    profile.location_text = "Poland"
    profile.country_code = "PL"
    profile.city = None
    profile.work_format = "remote"
    profile.english_level = "b2"
    profile.preferred_domains_json = ["saas"]
    profile.show_take_home_task_roles = True
    profile.show_live_coding_roles = False

    result = service.execute_ready_action(
        user=user,
        raw_message_id="raw-ready-update-2",
        action="update_matching_preferences",
        structured_payload={"work_format": "hybrid"},
    )

    assert result is not None
    assert result.status == "preferences_updated_needs_follow_up"
    assert profile.work_format == "hybrid"
    assert profile.questions_context_json["current_question_key"] == "location"
    assert "one more thing" in result.notification_text.lower()
    assert len(service.queue.messages) == 0


def test_execute_ready_action_records_matching_feedback() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_READY)

    result = service.execute_ready_action(
        user=user,
        raw_message_id="raw-ready-feedback-1",
        action="record_matching_feedback",
        structured_payload={
            "feedback_text": "These roles keep missing on salary and they often include live coding.",
            "source_stage": "VACANCY_REVIEW",
        },
    )

    assert result is not None
    assert result.status == "matching_feedback_recorded"
    feedback = profile.questions_context_json["matching_feedback"]["candidate_feedback_events"][-1]
    assert feedback["text"] == "These roles keep missing on salary and they often include live coding."
    assert "compensation" in feedback["categories"]
    assert "process" in feedback["categories"]
    assert feedback["source_stage"] == "VACANCY_REVIEW"
    assert "saved" in result.notification_text.lower()
    assert len(service.queue.messages) == 0


def test_verification_instruction_is_returned_for_non_video_input() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_verifications = FakeCandidateVerificationsRepository()
    service.repo = fake_repo
    service.verifications = fake_verifications
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_VERIFICATION_PENDING)

    result = service.handle_verification_submission(
        user=user,
        raw_message_id=uuid4(),
        content_type="voice",
    )

    assert result is not None
    assert result.status == "instruction"
    assert "video" in result.notification_text.lower()
    assert profile.state == CANDIDATE_STATE_VERIFICATION_PENDING
    assert len(fake_verifications.rows) == 1


def test_verification_rejects_video_with_wrong_phrase() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_verifications = FakeCandidateVerificationsRepository()
    service.repo = fake_repo
    service.verifications = fake_verifications
    service.files = SimpleNamespace(get_by_id=lambda _file_id: SimpleNamespace(id=_file_id, kind="video"))
    service.state_service = fake_state
    service.queue = FakeQueue()

    class _FakeIngestion:
        def __init__(self, _session):
            return None

        def ingest_file(self, _file_row, *, prompt_text=None):
            assert prompt_text == "Helly check: sync complete"
            return SimpleNamespace(text="Helly check green deploy")

    import src.candidate_profile.service as candidate_service_module

    original_ingestion = candidate_service_module.ContentIngestionService
    candidate_service_module.ContentIngestionService = _FakeIngestion

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_VERIFICATION_PENDING)
    verification = fake_verifications.create(
        profile_id=profile.id,
        attempt_no=1,
        phrase_text="Helly check: sync complete",
    )

    try:
        result = service.handle_verification_submission(
            user=user,
            raw_message_id=uuid4(),
            content_type="video",
            file_id=uuid4(),
        )
    finally:
        candidate_service_module.ContentIngestionService = original_ingestion

    assert result is not None
    assert result.status == "phrase_mismatch"
    assert profile.state == CANDIDATE_STATE_VERIFICATION_PENDING
    assert verification.status == "issued"
    assert verification.review_notes_json["phrase_matched"] is False
    assert 'I heard on the video: "Helly check green deploy".' in result.notification_text
    assert 'You were supposed to say: "Helly check: sync complete".' in result.notification_text
    assert service.queue.messages == []


def test_verification_accepts_cyrillic_transcript_of_expected_phrase() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_verifications = FakeCandidateVerificationsRepository()
    service.repo = fake_repo
    service.verifications = fake_verifications
    service.files = SimpleNamespace(get_by_id=lambda _file_id: SimpleNamespace(id=_file_id, kind="video"))
    service.state_service = fake_state
    service.queue = FakeQueue()

    class _FakeIngestion:
        def __init__(self, _session):
            return None

        def ingest_file(self, _file_row, *, prompt_text=None):
            assert prompt_text == "Helly check: stable build"
            return SimpleNamespace(text="Хелли чек. Стейбл билд.")

    import src.candidate_profile.service as candidate_service_module

    original_ingestion = candidate_service_module.ContentIngestionService
    candidate_service_module.ContentIngestionService = _FakeIngestion

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_VERIFICATION_PENDING)
    fake_verifications.create(
        profile_id=profile.id,
        attempt_no=1,
        phrase_text="Helly check: stable build",
    )

    try:
        result = service.handle_verification_submission(
            user=user,
            raw_message_id=uuid4(),
            content_type="video",
            file_id=uuid4(),
        )
    finally:
        candidate_service_module.ContentIngestionService = original_ingestion

    assert result is not None
    assert result.status == "completed"
    assert profile.state == CANDIDATE_STATE_READY
    assert profile.ready_at == "now"
    assert len(service.queue.messages) == 1
