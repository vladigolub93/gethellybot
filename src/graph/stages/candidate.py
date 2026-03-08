from __future__ import annotations

import re

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.graph.state import HellyGraphState
from src.llm.service import (
    safe_candidate_cv_decision,
    safe_candidate_questions_decision,
    safe_candidate_summary_review_decision,
    safe_interview_invitation_decision,
    safe_interview_in_progress_decision,
    safe_parse_candidate_questions,
    safe_state_assistance_decision,
)
from src.orchestrator.policy import resolve_state_context
from src.shared.text import normalize_command_text

def _candidate_verification_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\bcannot\b",
        r"\bcan't\b",
        r"\bcant\b",
        r"\blater\b",
        r"\bdesktop\b",
        r"\bcamera\b",
        r"\bvideo\b",
        r"\bphrase\b",
        r"\bwhat happens after\b",
        r"\bwhat next\b",
    )


def _candidate_ready_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhat happens now\b",
        r"\bwhat do i do next\b",
        r"\bwhat should i do next\b",
        r"\bwhen .*job\b",
        r"\bwhen .*opportunit",
        r"\bwhen .*match\b",
        r"\bhow .*matching\b",
        r"\bdo i need to do anything\b",
        r"\bdo i need anything else\b",
        r"\bwhen .*manager see\b",
        r"\bwhen will i hear\b",
    )


def load_candidate_stage_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    state.recent_context = [context.guidance_text]
    return state


def load_candidate_stage_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state

def _is_candidate_verification_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _candidate_verification_help_patterns())


def _is_candidate_ready_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _candidate_ready_help_patterns())


def _detect_candidate_ready_action(text: str) -> tuple[str | None, dict]:
    command = normalize_command_text(text or "")
    if command in {"delete profile", "delete my profile", "remove profile"}:
        return "delete_profile", {}
    return None, {}


def build_candidate_stage_detect_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        text = state.latest_user_message or ""
        if state.active_stage == "CV_PENDING":
            decision = safe_candidate_cv_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("cv_text"):
                state.structured_payload = {"cv_text": payload.get("cv_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "SUMMARY_REVIEW":
            decision = safe_candidate_summary_review_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            elif state.intent == "needs_clarification":
                state.parsed_input["intent"] = "needs_clarification"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("edit_text"):
                state.structured_payload = {"edit_text": payload.get("edit_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "QUESTIONS_PENDING":
            decision = safe_candidate_questions_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") == "send_salary_location_work_format":
                answer_text = payload.get("answer_text") or text
                parsed_payload = safe_parse_candidate_questions(session, answer_text).payload
                if parsed_payload:
                    state.proposed_action = "send_salary_location_work_format"
                    state.structured_payload = parsed_payload
                    state.parsed_input["intent"] = "stage_completion_input"
                else:
                    state.parsed_input["intent"] = "help"
                    state.follow_up_needed = True
                    state.follow_up_question = (
                        payload.get("response_text")
                        or "Please include your salary expectations, current location, and preferred work format."
                    )
            else:
                state.parsed_input["intent"] = "help"
                if payload.get("needs_follow_up"):
                    state.follow_up_needed = True
                    state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "VERIFICATION_PENDING":
            if state.latest_message_type == "video":
                state.intent = "stage_completion_input"
                state.parsed_input["intent"] = "stage_completion_input"
                state.proposed_action = "send_verification_video"
                state.structured_payload = {"submission_type": "video"}
                return state
            is_help = _is_candidate_verification_help(text)
        elif state.active_stage == "READY":
            if _is_candidate_ready_help(text):
                state.intent = "help"
                state.parsed_input["intent"] = "help"
                return state
            proposed_action, payload = _detect_candidate_ready_action(text)
            if proposed_action is not None:
                state.intent = "stage_completion_input"
                state.parsed_input["intent"] = "stage_completion_input"
                state.proposed_action = proposed_action
                state.structured_payload = payload
                return state
            is_help = False
        elif state.active_stage == "INTERVIEW_INVITED":
            decision = safe_interview_invitation_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "INTERVIEW_IN_PROGRESS":
            current_question_text = None
            try:
                candidates = CandidateProfilesRepository(session)
                interviews = InterviewsRepository(session)
                candidate = candidates.get_active_by_user_id(state.user_id)
                if candidate is not None:
                    active_session = interviews.get_active_session_for_candidate(candidate.id)
                    if active_session is not None:
                        question = interviews.get_question_by_order(
                            active_session.id,
                            active_session.current_question_order,
                        )
                        if question is not None:
                            current_question_text = question.question_text
            except Exception:
                current_question_text = None

            decision = safe_interview_in_progress_decision(
                session,
                latest_user_message=text,
                current_question_text=current_question_text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("answer_text"):
                state.structured_payload = {"answer_text": payload.get("answer_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        else:
            is_help = False
        state.parsed_input["intent"] = "help" if is_help else "candidate_input"
        return state

    return _node


def detect_candidate_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "CV_PENDING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "SUMMARY_REVIEW":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "QUESTIONS_PENDING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "VERIFICATION_PENDING":
        if state.latest_message_type == "video":
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = "send_verification_video"
            state.structured_payload = {"submission_type": "video"}
            return state
        is_help = _is_candidate_verification_help(text)
    elif state.active_stage == "READY":
        if _is_candidate_ready_help(text):
            state.intent = "help"
            state.parsed_input["intent"] = "help"
            return state
        proposed_action, payload = _detect_candidate_ready_action(text)
        if proposed_action is not None:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = proposed_action
            state.structured_payload = payload
            return state
        is_help = False
    elif state.active_stage == "INTERVIEW_INVITED":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "INTERVIEW_IN_PROGRESS":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    else:
        is_help = False
    state.parsed_input["intent"] = "help" if is_help else "candidate_input"
    return state


def build_candidate_stage_reply_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        context = resolve_state_context(role=state.role, state=state.active_stage)
        state.stage_status = "in_progress"
        state.follow_up_needed = False
        state.confidence = 0.85
        if state.parsed_input.get("intent") == "help":
            result = safe_state_assistance_decision(
                session,
                context=context,
                latest_user_message=state.latest_user_message,
                recent_context=state.knowledge_snippets,
            )
            state.reply_text = result.payload.get("response_text") or context.help_text or context.guidance_text
            state.follow_up_needed = True
            state.follow_up_question = context.guidance_text
            return state

        if state.active_stage == "CV_PENDING" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this experience summary to prepare your profile."
            state.confidence = 0.9
            return state

        if state.active_stage == "SUMMARY_REVIEW":
            if state.parsed_input.get("intent") == "needs_clarification":
                state.reply_text = "Tell me exactly what is incorrect in the summary, and I will update it once."
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            if state.parsed_input.get("intent") == "help":
                state.reply_text = state.reply_text or context.help_text or context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            if state.parsed_input.get("intent") == "stage_completion_input":
                state.stage_status = "ready_for_transition"
                if state.proposed_action == "approve_summary":
                    state.reply_text = state.reply_text or "Thanks. I will approve the summary and move to the next step."
                else:
                    state.reply_text = state.reply_text or "Thanks. I will update the summary based on your correction."
                state.confidence = 0.9
                return state

        if state.active_stage == "QUESTIONS_PENDING":
            if state.parsed_input.get("intent") == "stage_completion_input" and state.proposed_action == "send_salary_location_work_format":
                state.stage_status = "ready_for_transition"
                state.reply_text = "Thanks. I will update your profile details from this answer."
                state.confidence = 0.9
            else:
                state.reply_text = state.reply_text or context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
            return state

        if (
            state.active_stage == "VERIFICATION_PENDING"
            and state.parsed_input.get("intent") == "stage_completion_input"
            and state.latest_message_type == "video"
        ):
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this video to complete your verification step."
            state.confidence = 0.95
            return state

        if state.active_stage == "READY" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "I can help you remove the profile if you want to stop using Helly."
            state.confidence = 0.9
            return state

        if state.active_stage == "INTERVIEW_INVITED" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "accept_interview":
                state.reply_text = "Thanks. I will start the interview."
            else:
                state.reply_text = "Understood. I will skip this opportunity."
            state.confidence = 0.9
            return state

        if state.active_stage == "INTERVIEW_IN_PROGRESS" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this answer and continue the interview."
            state.confidence = 0.9
            return state

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
