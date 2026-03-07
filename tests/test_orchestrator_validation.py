from src.orchestrator.validation import normalize_action_name, validate_action_proposal


def test_normalize_action_name_normalizes_spaces_and_case() -> None:
    assert normalize_action_name("Approve Candidate") == "approve_candidate"


def test_validate_action_proposal_accepts_allowed_action() -> None:
    result = validate_action_proposal(
        state="MANAGER_REVIEW",
        role="hiring_manager",
        source="state_assistance",
        action="Approve Candidate",
        allowed_actions=["approve_candidate", "reject_candidate"],
        blocked_actions=[],
    )

    assert result.accepted is True
    assert result.normalized_action == "approve_candidate"
    assert result.reason_code == "validated"


def test_validate_action_proposal_rejects_disallowed_action() -> None:
    result = validate_action_proposal(
        state="READY",
        role="candidate",
        source="bot_controller",
        action="approve_candidate",
        allowed_actions=["wait_for_match", "delete_profile"],
        blocked_actions=[],
    )

    assert result.accepted is False
    assert result.normalized_action == "approve_candidate"
    assert result.reason_code == "action_not_allowed_for_state"


def test_validate_action_proposal_rejects_blocked_action() -> None:
    result = validate_action_proposal(
        state="SUMMARY_REVIEW",
        role="candidate",
        source="state_assistance",
        action="request_summary_change",
        allowed_actions=["approve_summary", "request_summary_change"],
        blocked_actions=["request_summary_change"],
    )

    assert result.accepted is False
    assert result.normalized_action == "request_summary_change"
    assert result.reason_code == "blocked_action"
