from __future__ import annotations

from src.graph.state import HellyGraphState
from src.llm.service import safe_delete_confirmation_decision, safe_state_assistance_decision
from src.orchestrator.policy import resolve_state_context


def _combined_recent_context(state: HellyGraphState) -> list[str]:
    combined: list[str] = []
    for item in list(state.recent_context) + list(state.knowledge_snippets):
        if item and item not in combined:
            combined.append(item)
    return combined


def load_delete_stage_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    if context.guidance_text and context.guidance_text not in state.recent_context:
        state.recent_context.append(context.guidance_text)
    return state


def load_delete_stage_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state


def detect_delete_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    state.parsed_input["intent"] = "help"
    return state


def build_delete_stage_reply_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        context = resolve_state_context(role=state.role, state=state.active_stage)
        entity_label = "profile" if state.role == "candidate" else "vacancy"
        state.stage_status = "in_progress"
        state.follow_up_needed = False
        state.confidence = 0.85
        decision = safe_delete_confirmation_decision(
            session,
            latest_user_message=state.latest_user_message,
            entity_label=entity_label,
            current_step_guidance=context.guidance_text,
            recent_context=_combined_recent_context(state),
        )
        payload = dict(decision.payload or {})
        state.intent = payload.get("intent") or "help"
        state.reply_text = payload.get("response_text")
        state.parsed_input["agent_reason_code"] = payload.get("reason_code")
        if payload.get("proposed_action") in {"confirm_delete", "cancel_delete"}:
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = payload.get("proposed_action")
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "confirm_delete":
                state.reply_text = state.reply_text or f"Understood. I will delete the {entity_label} now."
            else:
                state.reply_text = state.reply_text or f"Understood. I will keep the {entity_label} active."
            state.confidence = 0.9
            return state

        if state.intent == "help":
            state.parsed_input["intent"] = "help"
        else:
            state.parsed_input["intent"] = "help"
        state.reply_text = state.reply_text or context.guidance_text
        state.follow_up_needed = True
        state.follow_up_question = state.reply_text
        return state

    return _node
