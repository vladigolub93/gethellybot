import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import urlencode

import pytest

from src.webapp.auth import TelegramWebAppAuthError, verify_telegram_webapp_init_data


def _build_init_data(*, bot_token: str, user_payload: dict, auth_date: Optional[int] = None) -> str:
    auth_date = auth_date or int(time.time())
    pairs = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user_payload, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        "{key}={value}".format(key=key, value=pairs[key])
        for key in sorted(pairs.keys())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    pairs["hash"] = signature
    return urlencode(pairs)


def test_verify_telegram_webapp_init_data_accepts_valid_payload() -> None:
    init_data = _build_init_data(
        bot_token="bot-token",
        user_payload={
            "id": 123456,
            "first_name": "Vlad",
            "last_name": "Golub",
            "username": "vlad",
        },
    )

    identity = verify_telegram_webapp_init_data(
        init_data=init_data,
        bot_token="bot-token",
        max_age_seconds=3600,
    )

    assert identity.telegram_user_id == 123456
    assert identity.display_name == "Vlad Golub"
    assert identity.username == "vlad"


def test_verify_telegram_webapp_init_data_rejects_bad_signature() -> None:
    init_data = _build_init_data(
        bot_token="bot-token",
        user_payload={"id": 123456, "first_name": "Vlad"},
    ) + "tampered=1"

    with pytest.raises(TelegramWebAppAuthError, match="signature is invalid"):
        verify_telegram_webapp_init_data(
            init_data=init_data,
            bot_token="bot-token",
            max_age_seconds=3600,
        )


def test_verify_telegram_webapp_init_data_rejects_expired_payload() -> None:
    init_data = _build_init_data(
        bot_token="bot-token",
        user_payload={"id": 123456, "first_name": "Vlad"},
        auth_date=int(time.time()) - 7200,
    )

    with pytest.raises(TelegramWebAppAuthError, match="has expired"):
        verify_telegram_webapp_init_data(
            init_data=init_data,
            bot_token="bot-token",
            max_age_seconds=60,
        )
