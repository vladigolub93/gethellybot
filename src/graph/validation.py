from __future__ import annotations

from dataclasses import dataclass

from src.graph.state import HellyGraphState
from src.orchestrator.validation import validate_action_proposal


@dataclass(frozen=True)
class GraphValidationResult:
    accepted: bool
    normalized_action: str | None
    reason_code: str
    source: str
    stage: str | None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "accepted": self.accepted,
            "normalized_action": self.normalized_action,
            "reason_code": self.reason_code,
            "source": self.source,
            "stage": self.stage,
        }


def validate_graph_action(
    state: HellyGraphState,
    *,
    source: str = "langgraph_stage_agent",
) -> GraphValidationResult:
    result = validate_action_proposal(
        state=state.active_stage or "UNKNOWN",
        role=state.role,
        source=source,
        action=state.proposed_action,
        allowed_actions=state.allowed_actions,
        blocked_actions=[],
    )
    return GraphValidationResult(
        accepted=result.accepted,
        normalized_action=result.normalized_action,
        reason_code=result.reason_code,
        source=source,
        stage=state.active_stage,
    )


def apply_validation_result(
    state: HellyGraphState,
    *,
    source: str = "langgraph_stage_agent",
) -> HellyGraphState:
    validation = validate_graph_action(state, source=source)
    state.validation_result = validation.as_dict()
    if validation.accepted:
        state.proposed_action = validation.normalized_action
    return state

