from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import (
    safe_contact_required_decision,
    safe_role_selection_decision,
    safe_state_assistance_decision,
)
from src.orchestrator.policy import resolve_state_context


def _entry_help_patterns(stage: str) -> tuple[str, ...]:
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


def build_entry_detect_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        normalized = _normalize_text(state.latest_user_message or "")
        if state.active_stage == "CONTACT_REQUIRED":
            decision = safe_contact_required_decision(
                session,
                latest_user_message=state.latest_user_message or "",
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=state.knowledge_snippets or state.recent_context,
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state

        if state.active_stage == "ROLE_SELECTION":
            decision = safe_role_selection_decision(
                session,
                latest_user_message=state.latest_user_message or "",
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
                state.structured_payload = {"role": payload.get("proposed_action")}
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state

        is_help = any(re.search(pattern, normalized) for pattern in _entry_help_patterns(state.active_stage or ""))
        if is_help:
            state.intent = "help"
            state.parsed_input["intent"] = "help"
        else:
            state.intent = "unknown"
            state.parsed_input["intent"] = "unknown"
        return state

    return _node


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
