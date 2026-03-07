from __future__ import annotations

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.consents import UserConsentsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_bot_controller_decision
from src.messaging.service import MessagingService
from src.orchestrator.policy import ResolvedStateContext, resolve_state_context


class BotControllerService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.consents = UserConsentsRepository(session)
        self.interviews = InterviewsRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.messaging = MessagingService(session)

    def build_recovery_message(self, *, user, latest_user_message: str) -> str:
        context = self._resolve_context(user)
        result = safe_bot_controller_decision(
            self.session,
            role=context.role,
            state=context.state,
            state_goal=context.goal,
            allowed_actions=context.allowed_actions,
            blocked_actions=context.blocked_actions,
            missing_requirements=context.missing_requirements,
            current_step_guidance=context.guidance_text,
            latest_user_message=latest_user_message,
            recent_context=[],
        )
        default_response = self._default_response(context)
        if context.state in {"CONTACT_REQUIRED", "CONSENT_REQUIRED", "ROLE_SELECTION"}:
            return default_response
        if result.payload.get("intent") == "small_talk":
            return self.messaging.compose_small_talk(
                latest_user_message=latest_user_message,
                current_step_guidance=default_response,
            )
        response_text = result.payload.get("response_text")
        if response_text:
            return response_text
        return default_response

    def _resolve_context(self, user) -> ResolvedStateContext:
        role = None
        if user.is_candidate:
            role = "candidate"
        elif user.is_hiring_manager:
            role = "hiring_manager"

        if not user.phone_number:
            return resolve_state_context(role=role, state="CONTACT_REQUIRED")
        if not self.consents.has_granted(user.id, "data_processing"):
            return resolve_state_context(role=role, state="CONSENT_REQUIRED")
        if role is None:
            return resolve_state_context(role=None, state="ROLE_SELECTION")

        if role == "candidate":
            candidate = self.candidates.get_active_by_user_id(user.id)
            if candidate is not None:
                interview = self.interviews.get_active_session_for_candidate(candidate.id)
                if interview is not None:
                    state = f"INTERVIEW_{interview.state}"
                    return resolve_state_context(role=role, state=state)
                return resolve_state_context(role=role, state=candidate.state)
            return resolve_state_context(role=role, state="CV_PENDING")

        vacancy = self.vacancies.get_latest_incomplete_by_manager_user_id(user.id)
        if vacancy is not None:
            return resolve_state_context(role=role, state=vacancy.state)
        return resolve_state_context(role=role, state="OPEN")

    def _default_response(self, context: ResolvedStateContext) -> str:
        if context.state == "CONTACT_REQUIRED":
            return context.guidance_text
        if context.state == "CONSENT_REQUIRED":
            return context.guidance_text
        if context.state == "ROLE_SELECTION":
            return self.messaging.compose_role_selection()
        if context.guidance_text:
            return context.guidance_text
        if context.allowed_actions:
            return f"Please continue with the current step. Expected actions: {', '.join(context.allowed_actions)}."
        return "Please continue with the current step."
