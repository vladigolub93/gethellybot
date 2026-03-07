from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context


def _candidate_cv_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\bskip\b",
        r"\blater\b",
        r"\blinkedin\b",
        r"\bpdf\b",
        r"\bno cv\b",
        r"\bno resume\b",
        r"\bdo not have\b",
        r"\bdon't have\b",
        r"\bdont have\b",
        r"\bwhat should i send\b",
        r"\bwhat do i send\b",
        r"\bwhat can i send\b",
        r"\bwhat next\b",
    )


def load_candidate_cv_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    state.recent_context = [context.guidance_text]
    return state


def load_candidate_cv_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state


def detect_candidate_cv_intent_node(state: HellyGraphState) -> HellyGraphState:
    normalized = " ".join((state.latest_user_message or "").lower().split())
    is_help = any(re.search(pattern, normalized) for pattern in _candidate_cv_help_patterns())
    if not is_help and len(normalized) <= 40 and "?" in normalized:
        is_help = True
    state.parsed_input["intent"] = "help" if is_help else "candidate_input"
    return state


def build_candidate_cv_reply_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        context = resolve_state_context(role=state.role, state=state.active_stage)
        if state.parsed_input.get("intent") == "help":
            result = safe_state_assistance_decision(
                session,
                context=context,
                latest_user_message=state.latest_user_message,
                recent_context=state.knowledge_snippets,
            )
            state.reply_text = result.payload.get("response_text") or context.help_text or context.guidance_text
            state.proposed_action = result.payload.get("suggested_action")
            return state

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
