from __future__ import annotations

from src.graph.registry import registry
from src.graph.state import HellyGraphState


class StageGraphRouter:
    def get_registered_stage(self, stage: str | None) -> str | None:
        if not stage:
            return None
        return stage if registry.get_definition(stage) is not None else None

    def build_initial_state(
        self,
        *,
        stage: str,
        user_id: str | None,
        telegram_chat_id: str | None,
        role: str | None,
        latest_user_message: str,
        latest_message_type: str | None,
        allowed_actions: list[str],
        missing_requirements: list[str],
        recent_context: list[str] | None = None,
    ) -> HellyGraphState:
        return HellyGraphState(
            user_id=user_id,
            telegram_chat_id=telegram_chat_id,
            role=role,
            active_stage=stage,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
            allowed_actions=list(allowed_actions),
            missing_requirements=list(missing_requirements),
            recent_context=list(recent_context or []),
        )
