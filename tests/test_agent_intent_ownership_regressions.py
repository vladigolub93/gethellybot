from __future__ import annotations

from types import SimpleNamespace

from src.graph.state import HellyGraphState
from src.graph.stages.candidate import build_candidate_stage_detect_node
from src.graph.stages.deletion import build_delete_stage_reply_node
from src.graph.stages.manager import build_manager_stage_detect_node


def _state(*, stage: str, message: str, role: str = "candidate") -> HellyGraphState:
    return HellyGraphState(
        user_id="user-1",
        role=role,
        active_stage=stage,
        latest_user_message=message,
        latest_message_type="text",
        knowledge_snippets=["helpful context"],
        recent_context=["helpful context"],
    )


def test_candidate_summary_review_timing_question_does_not_trigger_transition(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_candidate_summary_review_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "This usually takes a few seconds.",
                "reason_code": "timing_question",
                "proposed_action": None,
            }
        ),
    )
    node = build_candidate_stage_detect_node(session=None)

    result = node(_state(stage="SUMMARY_REVIEW", message="How long will this take?"))

    assert result.proposed_action is None
    assert result.parsed_input["intent"] == "help"
    assert result.reply_text == "This usually takes a few seconds."


def test_candidate_summary_review_only_explicit_correction_creates_change_action(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_candidate_summary_review_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "stage_completion_input",
                "response_text": "I will update the summary.",
                "reason_code": "explicit_correction",
                "proposed_action": "request_summary_change",
                "edit_text": "Please emphasize Go and platform ownership.",
            }
        ),
    )
    node = build_candidate_stage_detect_node(session=None)

    result = node(
        _state(
            stage="SUMMARY_REVIEW",
            message="Please emphasize Go and platform ownership.",
        )
    )

    assert result.proposed_action == "request_summary_change"
    assert result.parsed_input["intent"] == "stage_completion_input"
    assert result.structured_payload["edit_text"] == "Please emphasize Go and platform ownership."


def test_candidate_questions_help_does_not_trigger_completion(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_candidate_questions_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Please answer in net salary terms.",
                "reason_code": "clarification_question",
                "proposed_action": None,
            }
        ),
    )
    node = build_candidate_stage_detect_node(session=None)

    result = node(_state(stage="QUESTIONS_PENDING", message="Gross or net?"))

    assert result.proposed_action is None
    assert result.parsed_input["intent"] == "help"


def test_vacancy_summary_review_timing_question_does_not_trigger_transition(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_summary_review_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "You can approve once the summary looks right.",
                "reason_code": "timing_question",
                "proposed_action": None,
            }
        ),
    )
    node = build_manager_stage_detect_node(session=None)

    result = node(_state(stage="VACANCY_SUMMARY_REVIEW", message="How long will this take?", role="manager"))

    assert result.proposed_action is None
    assert result.parsed_input["intent"] == "help"


def test_vacancy_summary_review_only_explicit_correction_creates_change_action(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_summary_review_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "stage_completion_input",
                "response_text": "I will update the vacancy summary.",
                "reason_code": "explicit_correction",
                "proposed_action": "request_summary_change",
                "edit_text": "This role is Go-first, not Python-first.",
            }
        ),
    )
    node = build_manager_stage_detect_node(session=None)

    result = node(
        _state(
            stage="VACANCY_SUMMARY_REVIEW",
            message="This role is Go-first, not Python-first.",
            role="manager",
        )
    )

    assert result.proposed_action == "request_summary_change"
    assert result.parsed_input["intent"] == "stage_completion_input"
    assert result.structured_payload["edit_text"] == "This role is Go-first, not Python-first."


def test_interview_in_progress_help_does_not_trigger_answer_action(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.candidate.safe_interview_in_progress_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Yes, you can answer by voice.",
                "reason_code": "format_question",
                "proposed_action": None,
            }
        ),
    )
    node = build_candidate_stage_detect_node(session=None)

    result = node(_state(stage="INTERVIEW_IN_PROGRESS", message="Can I answer by voice?"))

    assert result.proposed_action is None
    assert result.parsed_input["intent"] == "help"


def test_delete_confirmation_help_does_not_confirm(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.deletion.safe_delete_confirmation_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "It will cancel active interviews and remove the profile from matching.",
                "reason_code": "consequence_question",
                "proposed_action": None,
            }
        ),
    )
    node = build_delete_stage_reply_node(session=None)

    result = node(_state(stage="DELETE_CONFIRMATION", message="What exactly will be cancelled?"))

    assert result.proposed_action is None
    assert result.parsed_input["intent"] == "help"


def test_delete_confirmation_explicit_confirm_creates_delete_action(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.deletion.safe_delete_confirmation_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "stage_completion_input",
                "response_text": "Understood. I will delete the profile now.",
                "reason_code": "explicit_confirm",
                "proposed_action": "confirm_delete",
            }
        ),
    )
    node = build_delete_stage_reply_node(session=None)

    result = node(_state(stage="DELETE_CONFIRMATION", message="Confirm delete"))

    assert result.proposed_action == "confirm_delete"
    assert result.parsed_input["intent"] == "stage_completion_input"
