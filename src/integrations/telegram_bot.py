from __future__ import annotations

import itertools
import threading
from typing import Optional

import httpx

from src.config.settings import get_settings


class TelegramBotClient:
    _stub_counter = itertools.count(50_000_000)
    _stub_lock = threading.Lock()

    def __init__(self, *, timeout_seconds: float = 20.0):
        settings = get_settings()
        if not settings.telegram_bot_token and not settings.telegram_disable_outbound:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
        self.token = settings.telegram_bot_token
        self.disable_outbound = settings.telegram_disable_outbound
        self.api_base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.file_base_url = f"https://api.telegram.org/file/bot{self.token}" if self.token else ""
        self.timeout_seconds = timeout_seconds

    @classmethod
    def _next_stub_message_id(cls) -> int:
        with cls._stub_lock:
            return next(cls._stub_counter)

    def send_text_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> dict:
        if self.disable_outbound:
            return {
                "message_id": self._next_stub_message_id(),
                "date": 0,
                "chat": {"id": chat_id, "type": "private"},
                "text": text,
                "reply_markup": reply_markup,
                "reply_to_message_id": reply_to_message_id,
            }
        body = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        if reply_to_message_id is not None:
            body["reply_to_message_id"] = int(reply_to_message_id)
            body["allow_sending_without_reply"] = True
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.api_base_url}/sendMessage",
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {payload}")
        return payload.get("result") or {}

    def answer_callback_query(self, *, callback_query_id: str, text: Optional[str] = None) -> dict:
        if self.disable_outbound:
            return {"ok": True, "callback_query_id": callback_query_id, "text": text}
        body = {"callback_query_id": callback_query_id}
        if text:
            body["text"] = text
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.api_base_url}/answerCallbackQuery",
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram answerCallbackQuery failed: {payload}")
        return payload

    def get_file(self, *, telegram_file_id: str) -> dict:
        if self.disable_outbound:
            return {
                "file_id": telegram_file_id,
                "file_unique_id": f"stub-{telegram_file_id}",
                "file_path": f"stub/{telegram_file_id}",
            }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.api_base_url}/getFile",
                params={"file_id": telegram_file_id},
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getFile failed: {payload}")
        return payload.get("result") or {}

    def download_file_bytes(self, *, file_path: str) -> bytes:
        if self.disable_outbound:
            return f"stub:{file_path}".encode("utf-8")
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(f"{self.file_base_url}/{file_path}")
            response.raise_for_status()
            return response.content
