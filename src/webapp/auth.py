from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Dict
from urllib.parse import parse_qsl


class TelegramWebAppAuthError(ValueError):
    """Raised when Telegram WebApp initData cannot be verified."""


@dataclass(frozen=True)
class TelegramWebAppIdentity:
    telegram_user_id: int
    first_name: str
    last_name: str
    username: str
    auth_date: int
    raw_user: Dict[str, object]

    @property
    def display_name(self) -> str:
        bits = [self.first_name.strip(), self.last_name.strip()]
        return " ".join(bit for bit in bits if bit).strip()


def verify_telegram_webapp_init_data(
    *,
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> TelegramWebAppIdentity:
    if not init_data or not init_data.strip():
        raise TelegramWebAppAuthError("Telegram initData is required.")
    if not bot_token:
        raise TelegramWebAppAuthError("Telegram bot token is not configured.")

    parsed_pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed_pairs.pop("hash", "")
    if not received_hash:
        raise TelegramWebAppAuthError("Telegram initData hash is missing.")

    data_check_string = "\n".join(
        "{key}={value}".format(key=key, value=parsed_pairs[key])
        for key in sorted(parsed_pairs.keys())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramWebAppAuthError("Telegram initData signature is invalid.")

    try:
        auth_date = int(parsed_pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise TelegramWebAppAuthError("Telegram initData auth_date is invalid.") from exc

    if auth_date <= 0:
        raise TelegramWebAppAuthError("Telegram initData auth_date is missing.")
    if max_age_seconds > 0 and int(time.time()) - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("Telegram initData has expired.")

    user_payload_raw = parsed_pairs.get("user")
    if not user_payload_raw:
        raise TelegramWebAppAuthError("Telegram initData user payload is missing.")
    try:
        user_payload = json.loads(user_payload_raw)
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError("Telegram initData user payload is invalid JSON.") from exc

    telegram_user_id = user_payload.get("id")
    if not telegram_user_id:
        raise TelegramWebAppAuthError("Telegram user id is missing in initData.")

    return TelegramWebAppIdentity(
        telegram_user_id=int(telegram_user_id),
        first_name=str(user_payload.get("first_name") or ""),
        last_name=str(user_payload.get("last_name") or ""),
        username=str(user_payload.get("username") or ""),
        auth_date=auth_date,
        raw_user=user_payload,
    )
