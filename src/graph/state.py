from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HellyGraphState:
    user_id: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    role: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    active_stage: Optional[str] = None
    intent: Optional[str] = None
    stage_status: Optional[str] = None
    allowed_actions: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    latest_user_message: str = ""
    latest_message_type: Optional[str] = None
    parsed_input: dict[str, Any] = field(default_factory=dict)
    proposed_action: Optional[str] = None
    structured_payload: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] = field(default_factory=dict)
    reply_text: Optional[str] = None
    follow_up_needed: bool = False
    follow_up_question: Optional[str] = None
    confidence: Optional[float] = None
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    next_stage: Optional[str] = None
    recent_context: list[str] = field(default_factory=list)
    knowledge_snippets: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "telegram_chat_id": self.telegram_chat_id,
            "role": self.role,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "active_stage": self.active_stage,
            "intent": self.intent,
            "stage_status": self.stage_status,
            "allowed_actions": list(self.allowed_actions),
            "missing_requirements": list(self.missing_requirements),
            "latest_user_message": self.latest_user_message,
            "latest_message_type": self.latest_message_type,
            "parsed_input": dict(self.parsed_input),
            "proposed_action": self.proposed_action,
            "structured_payload": dict(self.structured_payload),
            "validation_result": dict(self.validation_result),
            "reply_text": self.reply_text,
            "follow_up_needed": self.follow_up_needed,
            "follow_up_question": self.follow_up_question,
            "confidence": self.confidence,
            "side_effects": list(self.side_effects),
            "next_stage": self.next_stage,
            "recent_context": list(self.recent_context),
            "knowledge_snippets": list(self.knowledge_snippets),
        }
