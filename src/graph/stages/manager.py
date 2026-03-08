from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import (
    safe_parse_vacancy_clarifications,
    safe_vacancy_clarification_decision,
    safe_state_assistance_decision,
    safe_vacancy_intake_decision,
    safe_vacancy_open_decision,
    safe_vacancy_summary_review_decision,
)
from src.orchestrator.policy import resolve_state_context
from src.shared.text import normalize_command_text

def _manager_review_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhat does this mean\b",
        r"\bhow should i read\b",
        r"\bexplain\b",
        r"\bwhat are the risks\b",
        r"\bwhat are the strengths\b",
        r"\bwhy was this candidate selected\b",
        r"\bwhat happens if i approve\b",
        r"\bwhat happens if i reject\b",
    )


def load_manager_stage_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    state.recent_context = [context.guidance_text]
    return state


def load_manager_stage_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state
def _is_manager_review_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _manager_review_help_patterns())


def _detect_manager_review_action(text: str) -> tuple[str | None, dict]:
    command = normalize_command_text(text or "")
    if command in {"approve candidate", "approve"}:
        return "approve_candidate", {}
    if command in {"reject candidate", "reject"}:
        return "reject_candidate", {}
    return None, {}


def build_manager_stage_detect_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        text = state.latest_user_message or ""
        if state.active_stage == "INTAKE_PENDING":
            decision = safe_vacancy_intake_decision(
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
            if payload.get("job_description_text"):
                state.structured_payload = {"job_description_text": payload.get("job_description_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        if state.active_stage == "CLARIFICATION_QA":
            decision = safe_vacancy_clarification_decision(
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
                parsed = dict(safe_parse_vacancy_clarifications(session, payload.get("answer_text") or text).payload or {})
                if parsed:
                    state.proposed_action = payload.get("proposed_action")
                    state.structured_payload = parsed
                    state.parsed_input["intent"] = "stage_completion_input"
                else:
                    state.parsed_input["intent"] = "needs_clarification"
                    state.intent = "needs_clarification"
                    state.follow_up_needed = True
                    state.follow_up_question = payload.get("response_text") or "Share the missing vacancy details in one message, and I will parse them for you."
            else:
                state.parsed_input["intent"] = "help"
            return state
        if state.active_stage == "VACANCY_SUMMARY_REVIEW":
            decision = safe_vacancy_summary_review_decision(
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
        if state.active_stage == "OPEN":
            decision = safe_vacancy_open_decision(
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
                state.structured_payload = {}
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        if state.active_stage == "MANAGER_REVIEW":
            if _is_manager_review_help(text):
                state.intent = "help"
                state.parsed_input["intent"] = "help"
                return state
            proposed_action, payload = _detect_manager_review_action(text)
            if proposed_action is not None:
                state.intent = "stage_completion_input"
                state.parsed_input["intent"] = "stage_completion_input"
                state.proposed_action = proposed_action
                state.structured_payload = payload
                return state
            is_help = False
        else:
            is_help = False
        state.parsed_input["intent"] = "help" if is_help else "manager_input"
        return state

    return _node


def detect_manager_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "INTAKE_PENDING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    if state.active_stage == "CLARIFICATION_QA":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    if state.active_stage == "VACANCY_SUMMARY_REVIEW":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    if state.active_stage == "OPEN":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    if state.active_stage == "MANAGER_REVIEW":
        if _is_manager_review_help(text):
            state.intent = "help"
            state.parsed_input["intent"] = "help"
            return state
        proposed_action, payload = _detect_manager_review_action(text)
        if proposed_action is not None:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = proposed_action
            state.structured_payload = payload
            return state
        is_help = False
    else:
        is_help = False
    state.parsed_input["intent"] = "help" if is_help else "manager_input"
    return state


def build_manager_stage_reply_node(session):
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

        if state.active_stage == "INTAKE_PENDING" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this job description to prepare the vacancy draft."
            state.confidence = 0.9
            return state

        if state.active_stage == "VACANCY_SUMMARY_REVIEW" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "approve_summary":
                state.reply_text = state.reply_text or "Understood. I will lock the summary and move to the required vacancy details."
            else:
                state.reply_text = state.reply_text or "Understood. I will update the vacancy summary based on your correction."
            state.confidence = 0.9
            return state

        if state.active_stage == "VACANCY_SUMMARY_REVIEW" and state.parsed_input.get("intent") == "needs_clarification":
            state.reply_text = "Tell me exactly what is incorrect in the vacancy summary, and I will update it once."
            state.follow_up_needed = True
            state.follow_up_question = state.reply_text
            return state

        if state.active_stage == "CLARIFICATION_QA" and state.parsed_input.get("intent") == "stage_completion_input":
            parsed = dict(state.structured_payload or {})
            if parsed:
                state.stage_status = "ready_for_transition"
                state.proposed_action = "send_vacancy_clarifications"
                state.structured_payload = parsed
                state.reply_text = "Thanks. I will update the vacancy details from this answer."
                state.confidence = 0.9
            else:
                state.reply_text = context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = context.guidance_text
            return state

        if state.active_stage == "CLARIFICATION_QA" and state.parsed_input.get("intent") == "needs_clarification":
            state.reply_text = (
                state.follow_up_question
                or "Share the missing vacancy details in one message, and I will parse them for you."
            )
            state.follow_up_needed = True
            state.follow_up_question = state.reply_text
            return state

        if state.active_stage == "OPEN" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "I can help you remove this vacancy if you want to stop matching for it."
            state.confidence = 0.9
            return state

        if state.active_stage == "MANAGER_REVIEW" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "approve_candidate":
                state.reply_text = "Understood. I will approve the candidate and prepare the handoff."
            else:
                state.reply_text = "Understood. I will reject the candidate."
            state.confidence = 0.9
            return state

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
