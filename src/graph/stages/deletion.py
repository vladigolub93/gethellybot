from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context
from src.shared.text import normalize_command_text


def _deletion_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhat happens\b",
        r"\bwhat exactly\b",
        r"\bwhat will be cancelled\b",
        r"\bwhich interviews\b",
        r"\bwhich matches\b",
        r"\bcan i cancel\b",
        r"\bhow do i cancel\b",
        r"\bundo\b",
        r"\bwhy\b",
        r"\bhelp\b",
    )


def load_delete_stage_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    state.recent_context = [context.guidance_text]
    return state


def load_delete_stage_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state


def _is_delete_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _deletion_help_patterns())


def _detect_delete_action(text: str) -> tuple[str | None, dict]:
    command = normalize_command_text(text or "")
    if command in {
        "confirm delete",
        "confirm delete profile",
        "confirm delete vacancy",
    }:
        return "confirm_delete", {}
    if command in {
        "cancel delete",
        "keep profile",
        "keep vacancy",
        "don't delete",
        "dont delete",
    }:
        return "cancel_delete", {}
    return None, {}


def detect_delete_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if _is_delete_help(text):
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    proposed_action, payload = _detect_delete_action(text)
    if proposed_action is not None:
        state.intent = "stage_completion_input"
        state.parsed_input["intent"] = "stage_completion_input"
        state.proposed_action = proposed_action
        state.structured_payload = payload
        return state
    state.parsed_input["intent"] = "delete_input"
    return state


def build_delete_stage_reply_node(session):
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

        if state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "confirm_delete":
                noun = "profile" if state.role == "candidate" else "vacancy"
                state.reply_text = f"Understood. I will delete the {noun} now."
            else:
                noun = "profile" if state.role == "candidate" else "vacancy"
                state.reply_text = f"Understood. I will keep the {noun} active."
            state.confidence = 0.9
            return state

        state.reply_text = context.guidance_text
        state.follow_up_needed = True
        state.follow_up_question = context.guidance_text
        return state

    return _node
