from __future__ import annotations

from typing import Any

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.integrations.telegram_bot import TelegramBotClient
from src.webapp.service import WebAppService


MAX_MATCH_ALERT_LENGTH = 3500


def _trim_text(value: str, *, limit: int = MAX_MATCH_ALERT_LENGTH) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


class TelegramMatchAlertService:
    def __init__(self, *, telegram: TelegramBotClient | None = None):
        self.settings = get_settings()
        self.telegram = telegram
        self.logger = get_logger(__name__)

    def is_enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_error_chat_id)

    def send_match_alert(
        self,
        *,
        event_type: str,
        match,
        vacancy=None,
        candidate_profile=None,
        candidate_version=None,
        candidate_user=None,
        manager_user=None,
        note: str | None = None,
    ) -> bool:
        if not self.is_enabled():
            return False
        try:
            telegram = self.telegram or TelegramBotClient()
            telegram.send_text_message(
                chat_id=int(self.settings.telegram_error_chat_id),
                text=self._build_message(
                    event_type=event_type,
                    match=match,
                    vacancy=vacancy,
                    candidate_profile=candidate_profile,
                    candidate_version=candidate_version,
                    candidate_user=candidate_user,
                    manager_user=manager_user,
                    note=note,
                ),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "telegram_match_alert_failed",
                event_type=event_type,
                match_id=str(getattr(match, "id", "") or ""),
                error=str(exc),
            )
            return False

    def _build_message(
        self,
        *,
        event_type: str,
        match,
        vacancy,
        candidate_profile,
        candidate_version,
        candidate_user,
        manager_user,
        note: str | None,
    ) -> str:
        candidate_name = WebAppService._candidate_display_name(
            candidate_user,
            candidate_version,
            getattr(candidate_user, "display_name", None) or "Candidate",
        )
        role_title = getattr(vacancy, "role_title", None) or "Unknown role"
        manager_name = (
            getattr(manager_user, "display_name", None)
            or getattr(manager_user, "username", None)
            or "Manager"
        )
        lines = [
            "Helly match alert",
            f"event: {event_type}",
            f"match_id: {getattr(match, 'id', '')}",
            f"status: {getattr(match, 'status', '')}",
            f"role: {role_title}",
            f"candidate: {candidate_name}",
            f"manager: {manager_name}",
            f"link: {getattr(self.settings, 'effective_admin_base_url', self.settings.app_base_url.rstrip('/'))}/admin#/matches/{getattr(match, 'id', '')}",
        ]
        if note:
            lines.append(f"note: {' '.join(str(note).split())}")
        return _trim_text("\n".join(lines))
