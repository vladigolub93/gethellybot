from __future__ import annotations

from src.graph.state import HellyGraphState
from src.graph.validation import apply_validation_result


def load_context_node(state: HellyGraphState) -> HellyGraphState:
    return state


def load_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    return state


def detect_intent_node(state: HellyGraphState) -> HellyGraphState:
    return state


def propose_action_node(state: HellyGraphState) -> HellyGraphState:
    return state


def validate_action_node(state: HellyGraphState) -> HellyGraphState:
    return apply_validation_result(state)


def emit_side_effects_node(state: HellyGraphState) -> HellyGraphState:
    return state
