from __future__ import annotations

from src.graph.nodes import (
    detect_intent_node,
    emit_side_effects_node,
    load_context_node,
    load_knowledge_node,
    propose_action_node,
    validate_action_node,
)
from src.graph.registry import registry
from src.graph.types import StageGraphDefinition


DEFAULT_STAGE_SEQUENCE = (
    "load_context",
    "load_knowledge",
    "detect_intent",
    "propose_action",
    "validate_action",
    "emit_side_effects",
)


def register_default_stage_graph(stage: str) -> None:
    registry.register_stage(
        definition=StageGraphDefinition(
            stage=stage,
            entry_node_name=DEFAULT_STAGE_SEQUENCE[0],
            terminal_node_names=("emit_side_effects",),
        ),
        nodes={
            "load_context": load_context_node,
            "load_knowledge": load_knowledge_node,
            "detect_intent": detect_intent_node,
            "propose_action": propose_action_node,
            "validate_action": validate_action_node,
            "emit_side_effects": emit_side_effects_node,
        },
    )


def register_foundation_stage_graphs() -> None:
    for stage in (
        "CONTACT_REQUIRED",
        "ROLE_SELECTION",
        "CV_PENDING",
        "SUMMARY_REVIEW",
        "QUESTIONS_PENDING",
        "VERIFICATION_PENDING",
        "READY",
        "INTAKE_PENDING",
        "VACANCY_SUMMARY_REVIEW",
        "CLARIFICATION_QA",
        "OPEN",
        "INTERVIEW_INVITED",
        "INTERVIEW_IN_PROGRESS",
        "MANAGER_REVIEW",
        "DELETE_CONFIRMATION",
    ):
        register_default_stage_graph(stage)
