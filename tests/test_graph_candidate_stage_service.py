from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class FakeCandidateProfilesRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get_active_by_user_id(self, user_id):
        return self.candidate


class FakeInterviewsRepository:
    def __init__(self, active_session=None):
        self.active_session = active_session

    def get_active_session_for_candidate(self, candidate_profile_id):
        return self.active_session


class FakeMatchesRepository:
    def __init__(self, invited_match=None):
        self.invited_match = invited_match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return self.invited_match


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
