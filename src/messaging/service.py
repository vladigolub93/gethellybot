from __future__ import annotations

from src.llm.service import (
    safe_build_interview_invitation_copy,
    safe_build_recovery_message,
    safe_build_role_selection_reply,
    safe_build_small_talk_reply,
    safe_copywrite_response,
)


class MessagingService:
    def __init__(self, session):
        self.session = session

    def compose(self, approved_intent: str) -> str:
        return safe_copywrite_response(
            self.session,
            approved_intent=approved_intent,
        ).payload["message"]

    def compose_small_talk(self, *, latest_user_message: str, current_step_guidance: str | None) -> str:
        return safe_build_small_talk_reply(
            self.session,
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
        ).payload["message"]

    def compose_recovery(self, *, state: str | None, allowed_actions: list[str], latest_user_message: str) -> str:
        return safe_build_recovery_message(
            self.session,
            state=state,
            allowed_actions=allowed_actions,
            latest_user_message=latest_user_message,
        ).payload["message"]

    def compose_role_selection(self, *, latest_user_message: str | None = None) -> str:
        return safe_build_role_selection_reply(
            self.session,
            latest_user_message=latest_user_message,
        ).payload["message"]

    def compose_interview_invitation(self, *, role_title: str | None) -> str:
        return safe_build_interview_invitation_copy(
            self.session,
            role_title=role_title,
        ).payload["message"]
