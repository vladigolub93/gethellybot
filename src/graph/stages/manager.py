from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_parse_vacancy_clarifications, safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context


def _manager_intake_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\bno formal jd\b",
        r"\bno jd\b",
        r"\bjust paste\b",
        r"\bpaste the job\b",
        r"\bwhat should i send\b",
        r"\bwhat do i include\b",
        r"\bwhat to include\b",
        r"\bwhat next\b",
        r"\bvoice\b",
        r"\btext\b",
    )


def _manager_clarification_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\bwhat exactly\b",
        r"\bwhat else\b",
        r"\bwhat do you need\b",
        r"\bwhat should i include\b",
        r"\bexample\b",
        r"\bgross or net\b",
        r"\bnet or gross\b",
        r"\bwhich currency\b",
        r"\bwhat currency\b",
        r"\bwhat period\b",
        r"\bwhat countries\b",
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


def _is_manager_intake_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if any(re.search(pattern, normalized) for pattern in _manager_intake_help_patterns()):
        return True
    return len(normalized) <= 40 and "?" in normalized


def _is_manager_clarification_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _manager_clarification_help_patterns())


def detect_manager_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "INTAKE_PENDING":
        is_help = _is_manager_intake_help(text)
        if is_help:
            state.intent = "help"
            state.parsed_input["intent"] = "help"
        else:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = "send_job_description_text"
            state.structured_payload = {"job_description_text": text.strip()}
        return state
    if state.active_stage == "CLARIFICATION_QA":
        if _is_manager_clarification_help(text):
            state.intent = "help"
            state.parsed_input["intent"] = "help"
        else:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
        return state
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

        if state.active_stage == "CLARIFICATION_QA" and state.parsed_input.get("intent") == "stage_completion_input":
            parsed = dict(safe_parse_vacancy_clarifications(session, state.latest_user_message).payload or {})
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

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
