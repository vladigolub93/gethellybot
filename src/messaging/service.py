from __future__ import annotations

from src.llm.service import safe_copywrite_response


class MessagingService:
    def __init__(self, session):
        self.session = session

    def compose(self, approved_intent: str) -> str:
        return safe_copywrite_response(
            self.session,
            approved_intent=approved_intent,
        ).payload["message"]
