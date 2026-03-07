from __future__ import annotations

import re

from src.graph.state import HellyGraphState
from src.llm.service import safe_parse_candidate_questions, safe_state_assistance_decision
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


def _detect_summary_review_action(text: str) -> tuple[str | None, dict]:
    normalized_text = (text or "").strip()
    command = normalize_command_text(text or "")
    if command in {"approve summary", "approve", "approve profile"}:
        return "approve_summary", {}
    if command in {"change summary", "edit summary", "change", "edit"}:
        return None, {"needs_edit_details": True}

    edit_text = normalized_text
    if command.startswith("edit summary:") or command.startswith("edit:"):
        edit_text = normalized_text.split(":", 1)[1].strip()

    if edit_text:
        return "request_summary_change", {"edit_text": edit_text}
    return None, {}


def _is_candidate_questions_help(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(re.search(pattern, normalized) for pattern in _candidate_questions_help_patterns())


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


def detect_candidate_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "CV_PENDING":
        is_help = _is_candidate_cv_help(text)
        if is_help:
            state.intent = "help"
            state.parsed_input["intent"] = "help"
        else:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = "send_cv_text"
            state.structured_payload = {"cv_text": text.strip()}
        return state
    elif state.active_stage == "SUMMARY_REVIEW":
        if _is_candidate_summary_help(text):
            state.intent = "help"
            state.parsed_input["intent"] = "help"
            return state
        proposed_action, payload = _detect_summary_review_action(text)
        if proposed_action is not None:
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = proposed_action
            state.structured_payload = payload
        else:
            state.intent = "needs_clarification"
            state.parsed_input["intent"] = "needs_clarification"
            state.structured_payload = payload
        return state
    elif state.active_stage == "QUESTIONS_PENDING":
        is_help = _is_candidate_questions_help(text)
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
            if state.parsed_input.get("intent") == "stage_completion_input":
                state.stage_status = "ready_for_transition"
                if state.proposed_action == "approve_summary":
                    state.reply_text = "Thanks. I will approve the summary and move to the next step."
                else:
                    state.reply_text = "Thanks. I will update the summary based on your correction."
                state.confidence = 0.9
                return state

        if state.active_stage == "QUESTIONS_PENDING" and state.parsed_input.get("intent") == "candidate_input":
            parsed = dict(safe_parse_candidate_questions(session, state.latest_user_message).payload or {})
            if parsed:
                state.stage_status = "ready_for_transition"
                state.proposed_action = "send_salary_location_work_format"
                state.structured_payload = parsed
                state.reply_text = "Thanks. I will update your profile details from this answer."
                state.confidence = 0.9
            else:
                state.reply_text = context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = context.guidance_text
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

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
