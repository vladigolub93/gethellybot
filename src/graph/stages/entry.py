from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context


def _entry_help_patterns(stage: str) -> tuple[str, ...]:
    if stage == "CONTACT_REQUIRED":
        return (
            r"\bwhy\b",
            r"\bhow\b",
            r"\bhelp\b",
            r"\bcontact\b",
            r"\bphone\b",
            r"\bnumber\b",
            r"\bskip\b",
            r"\blater\b",
            r"\bprivacy\b",
        )
    if stage == "CONSENT_REQUIRED":
        return (
            r"\bwhy\b",
            r"\bhow\b",
            r"\bhelp\b",
            r"\bconsent\b",
            r"\bprivacy\b",
            r"\bdata\b",
            r"\bstore\b",
            r"\bskip\b",
            r"\blater\b",
        )
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\brole\b",
        r"\bcandidate\b",
        r"\bhiring manager\b",
        r"\bdifference\b",
        r"\bwhich\b",
    )


def load_entry_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    state.recent_context = [context.guidance_text]
    return state


def load_entry_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state


def detect_entry_intent_node(state: HellyGraphState) -> HellyGraphState:
    normalized = " ".join((state.latest_user_message or "").lower().split())
    is_help = any(re.search(pattern, normalized) for pattern in _entry_help_patterns(state.active_stage or ""))
    state.parsed_input["intent"] = "help" if is_help else "unknown"
    return state


def build_entry_reply_node(session):
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
        else:
            state.reply_text = context.guidance_text
        return state

    return _node

