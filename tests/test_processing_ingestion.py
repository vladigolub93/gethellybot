from types import SimpleNamespace
from uuid import uuid4

from src.candidate_profile.processing import CandidateProcessingService
from src.interview.processing import InterviewProcessingService
from src.llm.service import LLMResult
from src.vacancy.processing import VacancyProcessingService


class FakeSessionForInterviewProcessing:
    def __init__(self, interview_session):
        self.interview_session = interview_session

    class _Result:
        def __init__(self, interview_session):
            self.interview_session = interview_session

        def scalar_one_or_none(self):
            return self.interview_session

    def execute(self, _stmt):
        return self._Result(self.interview_session)

    def add(self, _obj):
        return None

    def flush(self):
        return None


class FakeCandidateRepo:
    def __init__(self, profile, version):
        self.profile = profile
        self.version = version

    def get_by_id(self, _profile_id):
        return self.profile

    def get_version_by_id(self, _version_id):
        return self.version

    def update_version_source_text(self, version, *, extracted_text=None, transcript_text=None):
        version.extracted_text = extracted_text
        version.transcript_text = transcript_text
        return version

    def update_version_analysis(self, version, **kwargs):
        for key, value in kwargs.items():
            setattr(version, key, value)
        return version

    def update_version_embedding(self, version, *, semantic_embedding):
        version.semantic_embedding = semantic_embedding
        return version


class FakeVacancyRepo:
    def __init__(self, vacancy, version=None):
        self.vacancy = vacancy
        self.version = version

    def get_by_id(self, _vacancy_id):
        return self.vacancy

    def get_version_by_id(self, _version_id):
        return self.version

    def update_version_embedding(self, version, *, semantic_embedding):
        version.semantic_embedding = semantic_embedding
        return version

    def update_version_source_text(self, version, *, extracted_text=None, transcript_text=None):
        version.extracted_text = extracted_text
        version.transcript_text = transcript_text
        return version

    def update_version_analysis(self, version, **kwargs):
        for key, value in kwargs.items():
            setattr(version, key, value)
        return version

    def update_clarifications(self, vacancy, **kwargs):
        for key, value in kwargs.items():
            setattr(vacancy, key, value)
        return vacancy


class FakeRawMessagesRepo:
    def __init__(self, raw_message):
        self.raw_message = raw_message

    def get_by_id(self, _raw_message_id):
        return self.raw_message

    def set_text_content(self, raw_message, text_content):
        raw_message.text_content = text_content
        return raw_message


class FakeNotificationsRepo:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeStateService:
    def transition(self, **kwargs):
        entity = kwargs["entity"]
        field = kwargs.get("state_field", "state")
        setattr(entity, field, kwargs["to_state"])


def test_candidate_processing_extracts_document_text_before_summary(monkeypatch) -> None:
    profile = SimpleNamespace(id=uuid4(), user_id=uuid4(), state="CV_PROCESSING")
    version = SimpleNamespace(
        id=uuid4(),
        source_type="document_upload",
        extracted_text=None,
        transcript_text=None,
        source_raw_message_id=None,
    )
    service = CandidateProcessingService(SimpleNamespace())
    service.repo = FakeCandidateRepo(profile, version)
    service.raw_messages = FakeRawMessagesRepo(SimpleNamespace(id=uuid4(), text_content=None))
    service.notifications = FakeNotificationsRepo()
    service.state_service = FakeStateService()
    service.ingestion = SimpleNamespace(
        ingest_candidate_version=lambda _version: SimpleNamespace(
            text="Python engineer with FastAPI and PostgreSQL.",
            mode="document_extract",
            source="document_pdf",
        )
    )

    captured = {}

    def _fake_extract(_session, source_text, source_type):
        captured["source_text"] = source_text
        captured["source_type"] = source_type
        return LLMResult(
            payload={
                "headline": "Python engineer",
                "experience_excerpt": source_text,
                "skills": ["python"],
                "approval_summary_text": "You are a Python engineer with relevant professional experience. Your main technical strengths include python. You have worked on software systems and products described in your background.",
            },
            model_name="gpt-5.4",
            prompt_version="candidate_cv_extract_llm_v1",
        )

    monkeypatch.setattr(
        "src.candidate_profile.processing.safe_extract_candidate_summary",
        _fake_extract,
    )

    result = service.process_job(
        SimpleNamespace(
            id=uuid4(),
            job_type="candidate_cv_extract_v1",
            payload_json={
                "candidate_profile_id": str(profile.id),
                "candidate_profile_version_id": str(version.id),
            },
        )
    )

    assert result["status"] == "summary_ready"
    assert captured["source_text"] == "Python engineer with FastAPI and PostgreSQL."
    assert captured["source_type"] == "document_upload"
    assert version.extracted_text == "Python engineer with FastAPI and PostgreSQL."
    assert version.summary_json["headline"] == "Python engineer"
    assert version.summary_json["approval_summary_text"].startswith("You are a Python engineer")
    assert service.notifications.rows


def test_vacancy_processing_transcribes_clarification_before_parse() -> None:
    vacancy = SimpleNamespace(id=uuid4(), manager_user_id=uuid4(), state="CLARIFICATION_QA")
    raw_message = SimpleNamespace(id=uuid4(), user_id=vacancy.manager_user_id, text_content=None, content_type="voice", file_id=uuid4())
    service = VacancyProcessingService(SimpleNamespace())
    service.repo = FakeVacancyRepo(vacancy)
    service.raw_messages = FakeRawMessagesRepo(raw_message)
    service.notifications = FakeNotificationsRepo()
    service.state_service = FakeStateService()
    service.ingestion = SimpleNamespace(
        ingest_raw_message=lambda _raw_message: SimpleNamespace(
            text="Budget 7000 to 9000 USD monthly, remote, Germany and Poland, team size 6.",
            mode="transcription",
            source="openai_audio",
        )
    )
    service.vacancy_service = SimpleNamespace(
        process_clarification_text=lambda **kwargs: SimpleNamespace(
            status="follow_up",
            notification_template="vacancy_follow_up",
            notification_text="Need project description.",
        )
    )

    result = service.process_job(
        SimpleNamespace(
            id=uuid4(),
            job_type="vacancy_clarification_parse_v1",
            payload_json={"vacancy_id": str(vacancy.id), "raw_message_id": str(raw_message.id)},
        )
    )

    assert result["status"] == "follow_up"
    assert raw_message.text_content.startswith("Budget 7000")
    assert service.notifications.rows[0].payload_json["text"] == "Need project description."


def test_vacancy_processing_extracts_document_text_before_summary_review(monkeypatch) -> None:
    vacancy = SimpleNamespace(id=uuid4(), manager_user_id=uuid4(), state="JD_PROCESSING")
    version = SimpleNamespace(
        id=uuid4(),
        source_type="document_upload",
        extracted_text=None,
        transcript_text=None,
        source_raw_message_id=None,
    )
    service = VacancyProcessingService(SimpleNamespace())
    service.repo = FakeVacancyRepo(vacancy, version)
    service.raw_messages = FakeRawMessagesRepo(SimpleNamespace(id=uuid4(), text_content=None))
    service.notifications = FakeNotificationsRepo()
    service.state_service = FakeStateService()
    service.ingestion = SimpleNamespace(
        ingest_vacancy_version=lambda _version: SimpleNamespace(
            text="Senior Python engineer for a fintech platform using FastAPI and PostgreSQL.",
            mode="document_extract",
            source="document_pdf",
        )
    )

    captured = {}

    def _fake_extract(_session, source_text, source_type):
        captured["source_text"] = source_text
        captured["source_type"] = source_type
        return LLMResult(
            payload={
                "summary": {
                    "status": "draft",
                    "source_type": source_type,
                    "role_title": "Senior Python Engineer",
                    "primary_tech_stack": ["python", "fastapi", "postgresql"],
                    "project_description_excerpt": source_text,
                    "approval_summary_text": (
                        "This vacancy is for a senior Python engineer. "
                        "The main stack includes python, fastapi, and postgresql. "
                        "The role is focused on a fintech product and related platform systems."
                    ),
                },
                "inconsistency_json": {"issues": []},
            },
            model_name="gpt-5.4",
            prompt_version="vacancy_jd_extract_llm_v1",
        )

    monkeypatch.setattr(
        "src.vacancy.processing.safe_extract_vacancy_summary",
        _fake_extract,
    )
    monkeypatch.setattr(
        "src.vacancy.processing.safe_detect_vacancy_inconsistencies",
        lambda *_args, **_kwargs: LLMResult(
            payload={"findings": []},
            model_name="gpt-5.4",
            prompt_version="vacancy_inconsistency_detect_llm_v1",
        ),
    )

    result = service.process_job(
        SimpleNamespace(
            id=uuid4(),
            job_type="vacancy_jd_extract_v1",
            payload_json={
                "vacancy_id": str(vacancy.id),
                "vacancy_version_id": str(version.id),
            },
        )
    )

    assert result["status"] == "summary_ready"
    assert captured["source_text"] == "Senior Python engineer for a fintech platform using FastAPI and PostgreSQL."
    assert version.extracted_text == captured["source_text"]
    assert version.approval_summary_text.startswith("This vacancy is for a senior Python engineer.")
    assert vacancy.state == "VACANCY_SUMMARY_REVIEW"
    assert service.notifications.rows[0].template_key == "vacancy_summary_ready_for_review"


def test_interview_processing_transcribes_answer_before_handling() -> None:
    interview_session = SimpleNamespace(id=uuid4(), state="IN_PROGRESS")
    raw_message = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        text_content=None,
        content_type="voice",
        file_id=uuid4(),
    )
    service = InterviewProcessingService(FakeSessionForInterviewProcessing(interview_session))
    service.raw_messages = FakeRawMessagesRepo(raw_message)
    service.ingestion = SimpleNamespace(
        ingest_raw_message=lambda _raw_message: SimpleNamespace(
            text="I designed the payments reconciliation flow and implemented the async workers.",
            mode="transcription",
            source="openai_audio",
        )
    )
    captured = {}
    service.service = SimpleNamespace(
        _handle_interview_answer_text=lambda **kwargs: captured.update(kwargs) or SimpleNamespace(
            status="next_question",
            notification_template="candidate_interview_next_question",
            notification_text="What was your main challenge there?",
        )
    )

    result = service.process_job(
        SimpleNamespace(
            job_type="interview_answer_process_v1",
            payload_json={
                "interview_session_id": str(interview_session.id),
                "raw_message_id": str(raw_message.id),
            },
        )
    )

    assert result["status"] == "next_question"
    assert raw_message.text_content.startswith("I designed the payments")
    assert captured["text"].startswith("I designed the payments")
    assert captured["store_as_transcript"] is True
