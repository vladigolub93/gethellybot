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


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _detect_entry_completion(stage: str, normalized: str) -> tuple[str | None, dict]:
    if stage == "ROLE_SELECTION":
        if normalized == "candidate":
            return "candidate", {"role": "candidate"}
        if normalized == "hiring manager":
            return "hiring manager", {"role": "hiring_manager"}
    return None, {}


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
    normalized = _normalize_text(state.latest_user_message or "")
    is_help = any(re.search(pattern, normalized) for pattern in _entry_help_patterns(state.active_stage or ""))
    proposed_action, structured_payload = _detect_entry_completion(state.active_stage or "", normalized)
    if proposed_action is not None:
        state.intent = "stage_completion_input"
        state.parsed_input["intent"] = "stage_completion_input"
        state.proposed_action = proposed_action
        state.structured_payload = structured_payload
    elif is_help:
        state.intent = "help"
        state.parsed_input["intent"] = "help"
    else:
        state.intent = "unknown"
        state.parsed_input["intent"] = "unknown"
    return state


def build_entry_reply_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        context = resolve_state_context(role=state.role, state=state.active_stage)
        state.stage_status = "in_progress"
        state.follow_up_needed = False
        state.confidence = 0.85
        if state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.active_stage == "ROLE_SELECTION":
                selected_role = state.structured_payload.get("role")
                if selected_role == "candidate":
                    state.reply_text = "Understood. I will start the candidate flow."
                else:
                    state.reply_text = "Understood. I will start the hiring manager flow."
            else:
                state.reply_text = context.guidance_text
        elif state.parsed_input.get("intent") == "help":
            result = safe_state_assistance_decision(
                session,
                context=context,
                latest_user_message=state.latest_user_message,
                recent_context=state.knowledge_snippets,
            )
            state.reply_text = result.payload.get("response_text") or context.help_text or context.guidance_text
            state.follow_up_needed = True
            state.follow_up_question = context.guidance_text
        else:
            state.reply_text = context.guidance_text
        return state

    return _node
