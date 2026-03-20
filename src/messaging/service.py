from __future__ import annotations

from src.llm.service import (
    safe_build_interview_invitation_copy,
    safe_build_match_card_copy,
    safe_build_recovery_message,
    safe_build_small_talk_reply,
)


class MessagingService:
    def __init__(self, session):
        self.session = session

    def compose(self, approved_intent: str) -> str:
        return str(approved_intent or "").strip()

    def compose_match_card(
        self,
        *,
        audience: str,
        role_title: str | None,
        candidate_name: str | None = None,
        candidate_summary: str | None = None,
        project_summary: str | None = None,
        fit_reason: str | None = None,
        compensation_details: str | None = None,
        process_details: str | None = None,
        fit_band_label: str | None = None,
        gap_context: str | None = None,
        action_hint: str | None = None,
        fallback_message: str,
    ) -> str:
        return safe_build_match_card_copy(
            self.session,
            audience=audience,
            role_title=role_title,
            candidate_name=candidate_name,
            candidate_summary=candidate_summary,
            project_summary=project_summary,
            fit_reason=fit_reason,
            compensation_details=compensation_details,
            process_details=process_details,
            fit_band_label=fit_band_label,
            gap_context=gap_context,
            action_hint=action_hint,
            fallback_message=fallback_message,
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
        return (
            "Hi. Choose your role to get started: Candidate if you're looking for a job, "
            "or Hiring Manager if you're hiring. Just send: Candidate or Hiring Manager."
        )

    def compose_interview_invitation(self, *, role_title: str | None) -> str:
        return safe_build_interview_invitation_copy(
            self.session,
            role_title=role_title,
        ).payload["message"]
