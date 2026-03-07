from __future__ import annotations

from typing import Optional

import httpx

from src.config.settings import get_settings


class TelegramBotClient:
    def __init__(self, *, timeout_seconds: float = 20.0):
        settings = get_settings()
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
        self.token = settings.telegram_bot_token
        self.api_base_url = f"https://api.telegram.org/bot{self.token}"
        self.file_base_url = f"https://api.telegram.org/file/bot{self.token}"
        self.timeout_seconds = timeout_seconds

    def send_text_message(self, *, chat_id: int, text: str) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.api_base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {payload}")
        return payload.get("result") or {}

    def get_file(self, *, telegram_file_id: str) -> dict:
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
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(f"{self.file_base_url}/{file_path}")
            response.raise_for_status()
            return response.content
