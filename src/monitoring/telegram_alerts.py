from __future__ import annotations

from datetime import datetime, timezone
from traceback import format_exception
from typing import Any, Mapping

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.integrations.telegram_bot import TelegramBotClient


MAX_TELEGRAM_ALERT_LENGTH = 3500
MAX_TELEGRAM_TRACEBACK_LINES = 8


def _trim_text(value: str, *, limit: int = MAX_TELEGRAM_ALERT_LENGTH) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _render_context(context: Mapping[str, Any] | None) -> str:
    if not context:
        return ""

    lines: list[str] = []
    for key, value in context.items():
        if value in (None, "", [], {}, ()):
            continue
        rendered = str(value).replace("\n", " ").strip()
        if rendered:
            lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def _render_traceback(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    lines = format_exception(type(exc), exc, exc.__traceback__)
    return "".join(lines[-MAX_TELEGRAM_TRACEBACK_LINES:]).strip()


class TelegramErrorAlertService:
    def __init__(self, *, telegram: TelegramBotClient | None = None):
        self.settings = get_settings()
        self.telegram = telegram
        self.logger = get_logger(__name__)

    def is_enabled(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_error_chat_id)

    def send_error_alert(
        self,
        *,
        source: str,
        summary: str,
        exc: BaseException | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        if not self.is_enabled():
            return False

        try:
            telegram = self.telegram or TelegramBotClient()
            telegram.send_text_message(
                chat_id=int(self.settings.telegram_error_chat_id),
                text=self._build_message(
                    source=source,
                    summary=summary,
                    exc=exc,
                    context=context,
                ),
            )
            return True
        except Exception as alert_exc:  # noqa: BLE001
            self.logger.warning(
                "telegram_error_alert_failed",
                source=source,
                error=str(alert_exc),
            )
            return False

    def _build_message(
        self,
        *,
        source: str,
        summary: str,
        exc: BaseException | None,
        context: Mapping[str, Any] | None,
    ) -> str:
        parts = [
            "Helly error alert",
            f"environment: {self.settings.app_env}",
            f"timestamp_utc: {datetime.now(timezone.utc).isoformat()}",
            f"source: {source}",
            f"summary: {summary.strip()}",
        ]
        rendered_context = _render_context(context)
        if rendered_context:
            parts.extend(["context:", rendered_context])
        rendered_traceback = _render_traceback(exc)
        if rendered_traceback:
            parts.extend(["traceback:", rendered_traceback])
        return _trim_text("\n".join(parts))
