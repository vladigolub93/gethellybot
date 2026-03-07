from __future__ import annotations

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.consents import UserConsentsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_bot_controller_decision


STATE_ALLOWED_ACTIONS = {
    "CONTACT_REQUIRED": ["share_contact"],
    "CONSENT_REQUIRED": ["reply_i_agree"],
    "ROLE_SELECTION": ["candidate", "hiring manager"],
    "CV_PENDING": ["send_cv_or_experience"],
    "CV_PROCESSING": ["wait_for_summary"],
    "SUMMARY_REVIEW": ["approve_summary", "edit_summary"],
    "QUESTIONS_PENDING": ["send_salary_location_work_format"],
    "VERIFICATION_PENDING": ["send_verification_video"],
    "READY": ["wait_for_match"],
    "INTAKE_PENDING": ["send_job_description"],
    "JD_PROCESSING": ["wait_for_analysis"],
    "CLARIFICATION_QA": ["send_vacancy_clarifications"],
    "OPEN": ["wait_for_matches"],
    "INTERVIEW_ACCEPTED": ["answer_current_question"],
    "INTERVIEW_IN_PROGRESS": ["answer_current_question"],
}


class BotControllerService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.consents = UserConsentsRepository(session)
        self.interviews = InterviewsRepository(session)
        self.vacancies = VacanciesRepository(session)

    def build_recovery_message(self, *, user, latest_user_message: str) -> str:
        role, state, allowed_actions = self._resolve_context(user)
        result = safe_bot_controller_decision(
            self.session,
            role=role,
            state=state,
            allowed_actions=allowed_actions,
            latest_user_message=latest_user_message,
            recent_context=[],
        )
        default_response = self._default_response(state, allowed_actions)
        if state in {"CONTACT_REQUIRED", "CONSENT_REQUIRED", "ROLE_SELECTION"}:
            return default_response
        return result.payload.get("response_text") or default_response

    def _resolve_context(self, user) -> tuple[str | None, str | None, list[str]]:
        role = None
        if user.is_candidate:
            role = "candidate"
        elif user.is_hiring_manager:
            role = "hiring_manager"

        if not user.phone_number:
            return role, "CONTACT_REQUIRED", STATE_ALLOWED_ACTIONS["CONTACT_REQUIRED"]
        if not self.consents.has_granted(user.id, "data_processing"):
            return role, "CONSENT_REQUIRED", STATE_ALLOWED_ACTIONS["CONSENT_REQUIRED"]
        if role is None:
            return None, "ROLE_SELECTION", STATE_ALLOWED_ACTIONS["ROLE_SELECTION"]

        if role == "candidate":
            candidate = self.candidates.get_active_by_user_id(user.id)
            if candidate is not None:
                interview = self.interviews.get_active_session_for_candidate(candidate.id)
                if interview is not None:
                    state = f"INTERVIEW_{interview.state}"
                    return role, state, STATE_ALLOWED_ACTIONS.get(state, ["answer_current_question"])
                return role, candidate.state, STATE_ALLOWED_ACTIONS.get(candidate.state, [])
            return role, "CV_PENDING", STATE_ALLOWED_ACTIONS["CV_PENDING"]

        vacancy = self.vacancies.get_latest_incomplete_by_manager_user_id(user.id)
        if vacancy is not None:
            return role, vacancy.state, STATE_ALLOWED_ACTIONS.get(vacancy.state, [])
        return role, "OPEN", STATE_ALLOWED_ACTIONS["OPEN"]

    def _default_response(self, state: str | None, allowed_actions: list[str]) -> str:
        if state == "CONTACT_REQUIRED":
            return "Please share your contact to continue."
        if state == "CONSENT_REQUIRED":
            return "Please confirm data processing consent by replying 'I agree'."
        if state == "ROLE_SELECTION":
            return "Choose your role: Candidate or Hiring Manager."
        if allowed_actions:
            return f"Please continue with the current step. Expected actions: {', '.join(allowed_actions)}."
        return "Please continue with the current step."
