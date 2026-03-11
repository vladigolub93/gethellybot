from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeRawMessagesRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_recent_text_context(self, *, user_id, limit=6):
        return list(self.rows)[:limit]


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class FakeCandidateProfilesRepository:
    def __init__(self, candidate, *, current_version=None, candidates_by_id=None):
        self.candidate = candidate
        self.current_version = current_version
        if candidates_by_id is None:
            candidates_by_id = {}
            if candidate is not None and getattr(candidate, "id", None) is not None:
                candidates_by_id[candidate.id] = candidate
        self.candidates_by_id = candidates_by_id

    def get_active_by_user_id(self, user_id):
        return self.candidate

    def get_by_id(self, profile_id):
        return self.candidates_by_id.get(profile_id)

    def get_current_version(self, profile):
        if self.current_version is None or profile is None:
            return None
        if getattr(profile, "id", None) != getattr(self.candidate, "id", None):
            return None
        return self.current_version


class FakeInterviewsRepository:
    def __init__(self, active_session=None):
        self.active_session = active_session

    def get_active_session_for_candidate(self, candidate_profile_id):
        return self.active_session


class FakeMatchesRepository:
    def __init__(self, invited_match=None, candidate_review_match=None):
        self.invited_match = invited_match
        self.candidate_review_match = candidate_review_match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return self.invited_match

    def get_latest_pre_interview_review_for_candidate(self, candidate_profile_id):
        return self.candidate_review_match

    def list_active_for_candidate(self, candidate_profile_id):
        return []


class FakeCvChallengesRepository:
    def __init__(self, *, completed_attempt=None, active_attempt=None):
        self.completed_attempt = completed_attempt
        self.active_attempt = active_attempt

    def get_latest_completed_for_candidate_profile(self, candidate_profile_id):
        return self.completed_attempt

    def get_latest_active_for_candidate_profile(self, candidate_profile_id):
        return self.active_attempt


def test_graph_candidate_stage_help_receives_saved_profile_memory(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_candidate_ready_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Let me check your saved profile.",
                "reason_code": "help",
            }
        ),
    )

    def _fake_assistance(_session, *, context, latest_user_message, recent_context=None):
        captured["context"] = context
        captured["latest_user_message"] = latest_user_message
        captured["recent_context"] = list(recent_context or [])
        return SimpleNamespace(payload={"response_text": "Here is your saved profile data.", "suggested_action": None})

    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_state_assistance_decision",
        _fake_assistance,
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.raw_messages = FakeRawMessagesRepository(rows=[])
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(
            id="cp-memory",
            state="READY",
            current_version_id="cpv-memory",
            salary_min=5500,
            salary_currency="USD",
            salary_period="month",
            location_text="Warsaw, Poland",
            work_format="remote",
        ),
        current_version=SimpleNamespace(
            id="cpv-memory",
            summary_json={
                "approval_summary_text": "You are a senior Python engineer with strong backend product experience.",
                "years_experience": 7,
                "skills": ["python", "postgresql"],
            },
        ),
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()
    service.cv_challenges = FakeCvChallengesRepository()

    user = SimpleNamespace(
        id="u-memory",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Can you remind me what salary expectations I already gave you?",
    )

    assert reply == "Here is your saved profile data."
    combined_context = " ".join(captured["recent_context"])
    assert "senior Python engineer" in combined_context
    assert "salary expectation 5500 USD per month" in combined_context
    assert "location Warsaw, Poland" in combined_context
    assert "work format remote" in combined_context


def test_graph_candidate_ready_help_receives_cv_challenge_memory(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_candidate_ready_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Let me check your waiting-stage context.",
                "reason_code": "help",
            }
        ),
    )

    def _fake_assistance(_session, *, context, latest_user_message, recent_context=None):
        captured["recent_context"] = list(recent_context or [])
        return SimpleNamespace(payload={"response_text": "Challenge note.", "suggested_action": None})

    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_state_assistance_decision",
        _fake_assistance,
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.raw_messages = FakeRawMessagesRepository(rows=[])
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(
            id="cp-ready-game",
            state="READY",
            current_version_id="cpv-ready-game",
        ),
        current_version=SimpleNamespace(
            id="cpv-ready-game",
            summary_json={
                "approval_summary_text": "You are a senior JavaScript engineer.",
                "skills": ["react", "node.js", "typescript", "docker"],
            },
        ),
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()
    service.cv_challenges = FakeCvChallengesRepository(
        completed_attempt=SimpleNamespace(
            finished_at=SimpleNamespace(isoformat=lambda: "2026-03-11T10:10:00+00:00"),
            won=False,
            score=7,
            stage_reached=2,
            result_json={"totalMistakes": 3, "missedSkills": ["Docker", "GraphQL"]},
        )
    )

    user = SimpleNamespace(
        id="u-ready-game",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Что мне делать пока жду вакансии? И да, я опять проиграл в игру.",
    )

    assert reply == "Challenge note."
    combined_context = " ".join(captured["recent_context"])
    assert "Helly CV Challenge is available" in combined_context
    assert "last run lost" in combined_context
    assert "score 7" in combined_context
    assert "missed skills: Docker; GraphQL" in combined_context


def test_graph_candidate_stage_handles_cv_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp1", state="CV_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u4",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="If I don't have a CV yet?",
    )

    assert reply is not None
    assert "cv" in reply.lower() or "experience" in reply.lower()


def test_graph_candidate_stage_does_not_treat_cv_question_as_submission() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp1q", state="CV_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u4q",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="If I don't have a CV yet?",
    )

    assert result is not None
    assert result.stage == "CV_PENDING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_handles_cv_processing_question() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp1p", state="CV_PROCESSING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u4p",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="?",
    )

    assert result is not None
    assert result.stage == "CV_PROCESSING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None
    assert "summary" in result.reply_text.lower() or "process" in result.reply_text.lower()


def test_graph_candidate_stage_accepts_real_cv_text_transition() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp2", state="CV_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u5",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL.",
    )

    assert result is not None
    assert result.stage == "CV_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_cv_text"
    assert result.stage_status == "ready_for_transition"
    assert "Senior backend engineer" in result.structured_payload["cv_text"]


def test_graph_candidate_stage_handles_summary_review_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp3", state="SUMMARY_REVIEW")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u6",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What should I change if something is wrong in this summary?",
    )

    assert reply is not None
    assert "summary" in reply.lower() or "approve" in reply.lower()


def test_graph_candidate_stage_does_not_treat_timing_question_as_summary_edit() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp3b", state="SUMMARY_REVIEW")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u6b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="How long will this take?",
    )

    assert result is not None
    assert result.stage == "SUMMARY_REVIEW"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_summary_review_correction() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp4", state="SUMMARY_REVIEW")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u7",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="The summary is wrong: I work mostly with Go, not Python.",
    )

    assert result is not None
    assert result.stage == "SUMMARY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "request_summary_change"
    assert "Go" in result.structured_payload["edit_text"]


def test_graph_candidate_stage_accepts_summary_approve() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp4a", state="SUMMARY_REVIEW")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u7a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve summary",
    )

    assert result is not None
    assert result.stage == "SUMMARY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "approve_summary"


def test_graph_candidate_stage_handles_delete_confirmation_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(
            id="cp4d",
            state="READY",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u7d",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What exactly will be cancelled if I confirm?",
    )

    assert reply is not None
    assert "confirm" in reply.lower() or "delete" in reply.lower()


def test_graph_candidate_stage_accepts_delete_confirmation() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(
            id="cp4e",
            state="READY",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u7e",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Confirm delete profile",
    )

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"
    assert result.action_accepted is True
    assert result.proposed_action == "confirm_delete"
    assert result.stage_status == "ready_for_transition"


def test_graph_candidate_stage_does_not_treat_delete_question_as_confirm() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(
            id="cp4f",
            state="READY",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u7f",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="What exactly will be cancelled if I confirm?",
    )

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_passes_repeated_question_context_to_state_assistance(monkeypatch) -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp4g", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()
    service.raw_messages = FakeRawMessagesRepository(
        [
            "User: So when do I hear back?",
            "Helly: Short version: once there is a strong match, I will ping you here.",
        ]
    )

    captured = {}

    def _fake_ready_decision(_session, *, latest_user_message, current_step_guidance, recent_context):
        captured["detect_recent_context"] = list(recent_context)
        return SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Let me answer that.",
                "reason_code": "status_question",
                "needs_follow_up": True,
            }
        )

    def _fake_state_assistance(_session, *, context, latest_user_message, recent_context):
        captured["reply_recent_context"] = list(recent_context)
        captured["latest_user_message"] = latest_user_message
        return SimpleNamespace(
            payload={
                "response_text": "Short version: I’ll message you here when there’s a strong match.",
            }
        )

    monkeypatch.setattr("src.graph.stages.candidate.safe_candidate_ready_decision", _fake_ready_decision)
    monkeypatch.setattr("src.graph.stages.candidate.safe_state_assistance_decision", _fake_state_assistance)

    user = SimpleNamespace(
        id="u7g",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="So when do I hear back?",
    )

    assert reply == "Short version: I’ll message you here when there’s a strong match."
    assert captured["latest_user_message"] == "So when do I hear back?"
    assert "User: So when do I hear back?" in captured["detect_recent_context"]
    assert "Helly: Short version: once there is a strong match, I will ping you here." in captured["reply_recent_context"]


def test_graph_candidate_stage_handles_questions_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp5", state="QUESTIONS_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u8",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Why do you need my salary and location?",
    )

    assert reply is not None
    assert "salary" in reply.lower() or "matching" in reply.lower()


def test_graph_candidate_stage_does_not_treat_questions_clarification_as_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp5a", state="QUESTIONS_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u8a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Gross or net?",
    )

    assert result is not None
    assert result.stage == "QUESTIONS_PENDING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_real_questions_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp6", state="QUESTIONS_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u9",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="3000 USD net per month. Location: Warsaw. Remote.",
    )

    assert result is not None
    assert result.stage == "QUESTIONS_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_salary_location_work_format"
    assert result.structured_payload["salary_min"] == 3000
    assert result.structured_payload["location_text"] == "Warsaw"
    assert result.structured_payload["work_format"] == "remote"


def test_graph_candidate_stage_handles_verification_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp7", state="VERIFICATION_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u10",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="I cannot record video now because I am on desktop.",
    )

    assert reply is not None
    assert "video" in reply.lower() or "later" in reply.lower()


def test_graph_candidate_stage_does_not_treat_verification_question_as_completion() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp7q", state="VERIFICATION_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u10q",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Can I do this later from another device?",
    )

    assert result is not None
    assert result.stage == "VERIFICATION_PENDING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_verification_video_submission() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp7a", state="VERIFICATION_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u10a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="",
        latest_message_type="video",
    )

    assert result is not None
    assert result.stage == "VERIFICATION_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_verification_video"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["submission_type"] == "video"


def test_graph_candidate_stage_handles_ready_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u11",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What should I do next?",
    )

    assert reply is not None
    assert "ready" in reply.lower() or "match" in reply.lower()


def test_graph_candidate_stage_does_not_treat_ready_status_question_as_delete() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8q", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u11q",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="When will I hear back?",
    )

    assert result is not None
    assert result.stage == "READY"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_ready_delete_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8a", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u11a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Delete profile",
    )

    assert result is not None
    assert result.stage == "READY"
    assert result.action_accepted is True
    assert result.proposed_action == "delete_profile"
    assert result.stage_status == "ready_for_transition"


def test_graph_candidate_stage_accepts_find_matching_vacancies_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8b", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u11b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Is there a vacancy for me right now?",
    )

    assert result is not None
    assert result.stage == "READY"
    assert result.action_accepted is True
    assert result.proposed_action == "find_matching_vacancies"
    assert result.stage_status == "ready_for_transition"
    assert result.reply_text is None


def test_graph_candidate_stage_handles_vacancy_review_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8c", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository(candidate_review_match=SimpleNamespace(id="m8c"))

    user = SimpleNamespace(
        id="u11c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="What happens after I apply?",
    )

    assert result is not None
    assert result.stage == "VACANCY_REVIEW"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_apply_to_vacancy_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8d", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository(candidate_review_match=SimpleNamespace(id="m8d"))

    user = SimpleNamespace(
        id="u11d",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Apply 2",
    )

    assert result is not None
    assert result.stage == "VACANCY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "apply_to_vacancy"
    assert result.structured_payload == {"vacancy_slot": 2}
    assert result.stage_status == "ready_for_transition"
    assert result.reply_text is None


def test_graph_candidate_stage_handles_interview_invited_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp9", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository(invited_match=SimpleNamespace(id="m1"))

    user = SimpleNamespace(
        id="u12",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="How long does the interview take and can I answer by voice?",
    )

    assert reply is not None
    assert "interview" in reply.lower() or "voice" in reply.lower()


def test_graph_candidate_stage_does_not_treat_interview_invited_question_as_accept() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp9q", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository(invited_match=SimpleNamespace(id="m1q"))

    user = SimpleNamespace(
        id="u12q",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="How long does the interview take?",
    )

    assert result is not None
    assert result.stage == "INTERVIEW_INVITED"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_interview_invite_accept() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp10", state="READY")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository(invited_match=SimpleNamespace(id="m2"))

    user = SimpleNamespace(
        id="u13",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Accept interview",
    )

    assert result is not None
    assert result.stage == "INTERVIEW_INVITED"
    assert result.action_accepted is True
    assert result.proposed_action == "accept_interview"
    assert result.stage_status == "ready_for_transition"


def test_graph_candidate_stage_handles_interview_in_progress_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp11", state="READY")
    )
    service.interviews = FakeInterviewsRepository(active_session=SimpleNamespace(id="s1"))
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u14",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Can you clarify what exactly you are asking?",
    )

    assert reply is not None
    assert "answer" in reply.lower() or "question" in reply.lower()


def test_graph_candidate_stage_does_not_treat_interview_clarification_as_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp11a", state="READY")
    )
    service.interviews = FakeInterviewsRepository(active_session=SimpleNamespace(id="s1a"))
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u14a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Can you clarify what exactly you are asking?",
    )

    assert result is not None
    assert result.stage == "INTERVIEW_IN_PROGRESS"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_candidate_stage_accepts_interview_in_progress_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp12", state="READY")
    )
    service.interviews = FakeInterviewsRepository(active_session=SimpleNamespace(id="s2"))
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u15",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="I designed the API boundary and implemented the background processing myself.",
    )

    assert result is not None
    assert result.stage == "INTERVIEW_IN_PROGRESS"
    assert result.action_accepted is True
    assert result.proposed_action == "answer_current_question"
    assert result.stage_status == "ready_for_transition"


def test_graph_candidate_stage_accepts_cancel_interview_while_in_progress() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp12b", state="READY")
    )
    service.interviews = FakeInterviewsRepository(active_session=SimpleNamespace(id="s2b"))
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u15b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Cancel interview",
    )

    assert result is not None
    assert result.stage == "INTERVIEW_IN_PROGRESS"
    assert result.action_accepted is True
    assert result.proposed_action == "cancel_interview"
    assert result.stage_status == "ready_for_transition"
