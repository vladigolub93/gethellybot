from src.graph.state import HellyGraphState
from src.graph.validation import apply_validation_result, validate_graph_action


def test_validate_graph_action_accepts_allowed_action() -> None:
    state = HellyGraphState(
        role="candidate",
        active_stage="CV_PENDING",
        allowed_actions=["send_cv_text", "send_cv_document", "send_cv_voice"],
        proposed_action="send cv text",
    )

    result = validate_graph_action(state)

    assert result.accepted is True
    assert result.normalized_action == "send_cv_text"
    assert result.reason_code == "validated"


def test_validate_graph_action_rejects_disallowed_action() -> None:
    state = HellyGraphState(
        role="candidate",
        active_stage="READY",
        allowed_actions=["wait_for_match", "delete_profile"],
        proposed_action="approve candidate",
    )

    result = validate_graph_action(state)

    assert result.accepted is False
    assert result.normalized_action == "approve_candidate"
    assert result.reason_code == "action_not_allowed_for_state"


def test_apply_validation_result_updates_state_payload() -> None:
    state = HellyGraphState(
        role="hiring_manager",
        active_stage="MANAGER_REVIEW",
        allowed_actions=["approve_candidate", "reject_candidate"],
        proposed_action="Approve Candidate",
    )

    updated = apply_validation_result(state)

    assert updated.proposed_action == "approve_candidate"
    assert updated.validation_result["accepted"] is True
    assert updated.validation_result["reason_code"] == "validated"
