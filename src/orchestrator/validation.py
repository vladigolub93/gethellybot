from __future__ import annotations

from dataclasses import dataclass

from src.config.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ActionValidationResult:
    accepted: bool
    normalized_action: str | None
    reason_code: str


def normalize_action_name(action: str | None) -> str | None:
    if action is None:
        return None
    normalized = action.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def validate_action_proposal(
    *,
    state: str,
    role: str | None,
    source: str,
    action: str | None,
    allowed_actions: list[str],
    blocked_actions: list[str] | None = None,
) -> ActionValidationResult:
    normalized_action = normalize_action_name(action)
    normalized_allowed = {item for item in (normalize_action_name(value) for value in allowed_actions) if item}
    normalized_blocked = {item for item in (normalize_action_name(value) for value in (blocked_actions or [])) if item}

    if normalized_action is None:
        return ActionValidationResult(
            accepted=False,
            normalized_action=None,
            reason_code="no_action_proposed",
        )

    if normalized_action in normalized_blocked:
        logger.info(
            "orchestrator_action_rejected",
            state=state,
            role=role,
            source=source,
            action=normalized_action,
            reason_code="blocked_action",
        )
        return ActionValidationResult(
            accepted=False,
            normalized_action=normalized_action,
            reason_code="blocked_action",
        )

    if normalized_action not in normalized_allowed:
        logger.info(
            "orchestrator_action_rejected",
            state=state,
            role=role,
            source=source,
            action=normalized_action,
            reason_code="action_not_allowed_for_state",
        )
        return ActionValidationResult(
            accepted=False,
            normalized_action=normalized_action,
            reason_code="action_not_allowed_for_state",
        )

    logger.info(
        "orchestrator_action_validated",
        state=state,
        role=role,
        source=source,
        action=normalized_action,
    )
    return ActionValidationResult(
        accepted=True,
        normalized_action=normalized_action,
        reason_code="validated",
    )
