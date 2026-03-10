from __future__ import annotations

import re

from src.candidate_profile.states import normalize_candidate_operational_state
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.identity.rules import has_primary_contact_channel
from src.llm.service import safe_bot_controller_decision, safe_state_assistance_decision
from src.messaging.service import MessagingService
from src.orchestrator.policy import ResolvedStateContext, resolve_state_context
from src.orchestrator.state_memory import build_state_memory
from src.orchestrator.validation import validate_action_proposal


class BotControllerService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.evaluations = EvaluationsRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matching = MatchingRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.messaging = MessagingService(session)

    def build_recovery_message(self, *, user, latest_user_message: str) -> str:
        context = self._resolve_context(user)
        memory = self._build_state_memory(user=user, context=context)
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
            recent_context=memory,
        )
        default_response = self._default_response(context)
        if context.state in {"CONTACT_REQUIRED", "ROLE_SELECTION"}:
            return default_response
        if result.payload.get("intent") == "small_talk":
            return self.messaging.compose_small_talk(
                latest_user_message=latest_user_message,
                current_step_guidance=default_response,
            )
        self._validate_action_from_result(
            context=context,
            source="bot_controller",
            action=result.payload.get("proposed_action"),
        )
        response_text = result.payload.get("response_text")
        if response_text:
            return response_text
        return default_response

    def maybe_build_in_state_assistance(self, *, user, latest_user_message: str) -> str | None:
        context = self._resolve_context(user)
        if not latest_user_message.strip():
            return None
        if context.state not in {
            "CONTACT_REQUIRED",
            "ROLE_SELECTION",
            "CV_PENDING",
            "INTAKE_PENDING",
            "SUMMARY_REVIEW",
            "QUESTIONS_PENDING",
            "VERIFICATION_PENDING",
            "CLARIFICATION_QA",
            "READY",
            "VACANCY_REVIEW",
            "OPEN",
            "PRE_INTERVIEW_REVIEW",
            "INTERVIEW_INVITED",
            "INTERVIEW_IN_PROGRESS",
            "MANAGER_REVIEW",
            "DELETE_CONFIRMATION",
        }:
            return None
        if not self._looks_like_help_or_constraint_message(
            state=context.state,
            latest_user_message=latest_user_message,
        ):
            return None

        result = safe_state_assistance_decision(
            self.session,
            context=context,
            latest_user_message=latest_user_message,
            recent_context=self._build_state_memory(user=user, context=context),
        )
        self._validate_action_from_result(
            context=context,
            source="state_assistance",
            action=result.payload.get("suggested_action"),
        )
        return result.payload.get("response_text") or context.help_text or context.guidance_text

    def _resolve_context(self, user) -> ResolvedStateContext:
        role = None
        if user.is_candidate:
            role = "candidate"
        elif user.is_hiring_manager:
            role = "hiring_manager"

        if not has_primary_contact_channel(user):
            return resolve_state_context(role=role, state="CONTACT_REQUIRED")
        if role is None:
            return resolve_state_context(role=None, state="ROLE_SELECTION")

        if role == "candidate":
            candidate = self.candidates.get_active_by_user_id(user.id)
            if candidate is not None:
                if self._has_pending_deletion(candidate):
                    return resolve_state_context(role=role, state="DELETE_CONFIRMATION")
                interview = self.interviews.get_active_session_for_candidate(candidate.id)
                if interview is not None:
                    state_map = {
                        "INVITED": "INTERVIEW_INVITED",
                        "ACCEPTED": "INTERVIEW_IN_PROGRESS",
                        "IN_PROGRESS": "INTERVIEW_IN_PROGRESS",
                    }
                    mapped_state = state_map.get(interview.state)
                    if mapped_state is not None:
                        return resolve_state_context(role=role, state=mapped_state)
                invited_match = self.matching.get_latest_invited_for_candidate(candidate.id)
                if invited_match is not None:
                    return resolve_state_context(role=role, state="INTERVIEW_INVITED")
                getter = getattr(self.matching, "get_latest_pre_interview_review_for_candidate", None)
                if callable(getter):
                    candidate_review_match = getter(candidate.id)
                    if candidate_review_match is not None:
                        return resolve_state_context(role=role, state="VACANCY_REVIEW")
                return resolve_state_context(
                    role=role,
                    state=normalize_candidate_operational_state(candidate.state),
                )
            return resolve_state_context(role=role, state="CV_PENDING")

        manager_vacancies = self.vacancies.get_by_manager_user_id(user.id)
        latest_active_vacancy = self.vacancies.get_latest_active_by_manager_user_id(user.id)
        if latest_active_vacancy is not None and self._has_pending_deletion(latest_active_vacancy):
            return resolve_state_context(role=role, state="DELETE_CONFIRMATION")
        review_match = self.matching.get_latest_manager_review_for_manager(
            [vacancy.id for vacancy in manager_vacancies]
        )
        if review_match is not None:
            return resolve_state_context(role=role, state="MANAGER_REVIEW")
        pre_interview_match = None
        getter = getattr(self.matching, "get_latest_pre_interview_review_for_manager", None)
        if callable(getter):
            pre_interview_match = getter([vacancy.id for vacancy in manager_vacancies])
        if pre_interview_match is not None:
            return resolve_state_context(role=role, state="PRE_INTERVIEW_REVIEW")

        vacancy = self.vacancies.get_latest_incomplete_by_manager_user_id(user.id)
        if vacancy is not None:
            return resolve_state_context(role=role, state=vacancy.state)
        return resolve_state_context(role=role, state="OPEN")

    def _default_response(self, context: ResolvedStateContext) -> str:
        if context.state == "CONTACT_REQUIRED":
            return context.guidance_text
        if context.state == "ROLE_SELECTION":
            return self.messaging.compose_role_selection()
        if context.guidance_text:
            return context.guidance_text
        if context.allowed_actions:
            return f"Please continue with the current step. Expected actions: {', '.join(context.allowed_actions)}."
        return "Please continue with the current step."

    def _build_state_memory(self, *, user, context: ResolvedStateContext) -> list[str]:
        return build_state_memory(
            role=context.role,
            stage=context.state,
            user_id=getattr(user, "id", None),
            candidates=self.candidates,
            vacancies=self.vacancies,
            matches=self.matching,
            interviews=self.interviews,
            evaluations=self.evaluations,
        )

    def _validate_action_from_result(self, *, context: ResolvedStateContext, source: str, action: str | None) -> None:
        validate_action_proposal(
            state=context.state,
            role=context.role,
            source=source,
            action=action,
            allowed_actions=context.allowed_actions,
            blocked_actions=context.blocked_actions,
        )

    def _looks_like_help_or_constraint_message(self, *, state: str, latest_user_message: str) -> bool:
        normalized = " ".join((latest_user_message or "").lower().split())
        if not normalized:
            return False

        patterns_by_state = {
            "CONTACT_REQUIRED": [
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhat for\b",
                r"\bwhat do i do\b",
                r"\bwhat should i do\b",
                r"\bcontact\b",
                r"\bphone\b",
                r"\bnumber\b",
                r"\bprivacy\b",
            ],
            "ROLE_SELECTION": [
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhat for\b",
                r"\brole\b",
                r"\bcandidate\b",
                r"\bhiring manager\b",
                r"\bchoose\b",
                r"\bwhich one\b",
                r"\bdifference\b",
            ],
            "CV_PENDING": [
                r"\bi do not have (a )?(cv|resume)\b",
                r"\bi don't have (a )?(cv|resume)\b",
                r"\bif i do not have\b",
                r"\bif i don't have\b",
                r"\bno (cv|resume)\b",
                r"\bwhat if\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcan i\b",
                r"\bwhy\b",
                r"\blinkedin\b",
                r"\bskip\b",
                r"\blater\b",
                r"\bfor now\b",
            ],
            "INTAKE_PENDING": [
                r"\bi do not have (a )?(jd|job description)\b",
                r"\bi don't have (a )?(jd|job description)\b",
                r"\bi do not have (a )?formal (jd|job description)\b",
                r"\bi don't have (a )?formal (jd|job description)\b",
                r"\bno (jd|job description)\b",
                r"\bno formal (jd|job description)\b",
                r"\bwhat if\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcan i\b",
                r"\bwhy\b",
            ],
            "QUESTIONS_PENDING": [
                r"\bwhy\b",
                r"\bwhat for\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcan i\b",
                r"\bgross\b",
                r"\bnet\b",
            ],
            "VERIFICATION_PENDING": [
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcan i\b",
                r"\bcamera\b",
                r"\bdesktop\b",
                r"\bvideo\b",
            ],
            "CLARIFICATION_QA": [
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcan i\b",
                r"\bwhat for\b",
            ],
            "SUMMARY_REVIEW": [
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhat does this mean\b",
                r"\bbased on what\b",
                r"\bwhere did you get\b",
                r"\bwhat should i change\b",
                r"\bwhat do i change\b",
                r"\bexplain\b",
            ],
            "READY": [
                r"\bwhat happens now\b",
                r"\bwhat now\b",
                r"\bwhat next\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhen\b",
                r"\bmatch\b",
                r"\bjobs?\b",
                r"\bopportunit(y|ies)\b",
                r"\bdelete\b",
            ],
            "VACANCY_REVIEW": [
                r"\bwhat\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhy\b",
                r"\bapply\b",
                r"\bskip\b",
                r"\bvacanc(?:y|ies)\b",
                r"\brole\b",
            ],
            "OPEN": [
                r"\bwhat happens now\b",
                r"\bwhat now\b",
                r"\bwhat next\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhen\b",
                r"\bcandidates?\b",
                r"\bmatches?\b",
                r"\bdelete\b",
                r"\bupdate\b",
            ],
            "INTERVIEW_INVITED": [
                r"\bwhat is this\b",
                r"\bwhat happens\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhy\b",
                r"\bhow long\b",
                r"\bduration\b",
                r"\bvoice\b",
                r"\bvideo\b",
            ],
            "INTERVIEW_IN_PROGRESS": [
                r"\bhow\b",
                r"\bhelp\b",
                r"\brepeat\b",
                r"\bwhat do you mean\b",
                r"\bclarify\b",
                r"\bvoice\b",
                r"\bvideo\b",
                r"\boff topic\b",
                r"\bcancel\b",
                r"\bstop\b",
                r"\baccept interview\b",
                r"\bskip opportunity\b",
            ],
            "MANAGER_REVIEW": [
                r"\bwhat does this mean\b",
                r"\bwhat do these scores mean\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhy\b",
                r"\bapprove\b",
                r"\breject\b",
                r"\bstrengths?\b",
                r"\brisks?\b",
            ],
            "PRE_INTERVIEW_REVIEW": [
                r"\bwhat does this mean\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bwhy\b",
                r"\bwhat happens after\b",
                r"\binterview\b",
                r"\bskip\b",
            ],
            "DELETE_CONFIRMATION": [
                r"\bwhat\b",
                r"\bwhy\b",
                r"\bhow\b",
                r"\bhelp\b",
                r"\bcancel\b",
                r"\bconfirm\b",
                r"\bdelete\b",
                r"\bremoved?\b",
                r"\bcancelled?\b",
                r"\binterviews?\b",
                r"\bmatches?\b",
                r"\bprofile\b",
                r"\bvacancy\b",
            ],
        }
        patterns = patterns_by_state.get(state, [])
        return any(re.search(pattern, normalized) for pattern in patterns)

    @staticmethod
    def _has_pending_deletion(entity) -> bool:
        context = getattr(entity, "questions_context_json", None) or {}
        deletion = context.get("deletion") or {}
        return bool(deletion.get("pending"))
