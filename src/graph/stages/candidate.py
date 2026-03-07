from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context
from src.shared.text import normalize_command_text


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


def _candidate_summary_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhat should i change\b",
        r"\bwhat kind of changes\b",
        r"\bwhere did .*summary come from\b",
        r"\bwhere does .*summary come from\b",
        r"\bwhy .*approval\b",
        r"\bwhy .*approve\b",
        r"\bhow .*summary\b",
        r"\bhelp .*summary\b",
        r"\bwhat if .*wrong\b",
    )


def _candidate_questions_help_patterns() -> tuple[str, ...]:
    return (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bhelp\b",
        r"\bwhat happens after\b",
        r"\bwhat next\b",
        r"\bexample\b",
        r"\bgross or net\b",
        r"\bnet or gross\b",
        r"\bwhich currency\b",
        r"\bwhat currency\b",
        r"\bwhat period\b",
        r"\bper month or year\b",
        r"\bhow should i answer\b",
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


def _is_candidate_cv_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if any(re.search(pattern, normalized) for pattern in _candidate_cv_help_patterns()):
        return True
    return len(normalized) <= 40 and "?" in normalized


def _is_candidate_summary_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    command = normalize_command_text(text or "")
    if command in {
        "approve summary",
        "approve",
        "approve profile",
        "change summary",
        "edit summary",
        "change",
        "edit",
    }:
        return False
    if command.startswith("edit summary:") or command.startswith("edit:"):
        return False
    if any(re.search(pattern, normalized) for pattern in _candidate_summary_help_patterns()):
        return True
    return False


def _is_candidate_questions_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _candidate_questions_help_patterns())


def detect_candidate_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "CV_PENDING":
        is_help = _is_candidate_cv_help(text)
    elif state.active_stage == "SUMMARY_REVIEW":
        is_help = _is_candidate_summary_help(text)
    elif state.active_stage == "QUESTIONS_PENDING":
        is_help = _is_candidate_questions_help(text)
    else:
        is_help = False
    state.parsed_input["intent"] = "help" if is_help else "candidate_input"
    return state


def build_candidate_stage_reply_node(session):
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
