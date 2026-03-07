from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_state_assistance_decision
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


def detect_manager_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "INTAKE_PENDING":
        is_help = _is_manager_intake_help(text)
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

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
