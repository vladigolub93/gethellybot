from types import SimpleNamespace

from src.monitoring.telegram_alerts import TelegramErrorAlertService


class FakeTelegramBotClient:
    def __init__(self) -> None:
        self.calls = []

    def send_text_message(self, *, chat_id, text, reply_markup=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return {"message_id": 1}


def test_send_error_alert_sends_message_when_enabled(monkeypatch) -> None:
    fake_telegram = FakeTelegramBotClient()
    monkeypatch.setattr(
        "src.monitoring.telegram_alerts.get_settings",
        lambda: SimpleNamespace(
            app_env="test",
            telegram_bot_token="token",
            telegram_error_chat_id=-100123,
        ),
    )

    service = TelegramErrorAlertService(telegram=fake_telegram)

    sent = service.send_error_alert(
        source="worker_process_once",
        summary="Worker failed.",
        exc=RuntimeError("boom"),
        context={"job_type": "matching_run_for_vacancy_v1"},
    )

    assert sent is True
    assert fake_telegram.calls[0]["chat_id"] == -100123
    assert "Helly error alert" in fake_telegram.calls[0]["text"]
    assert "source: worker_process_once" in fake_telegram.calls[0]["text"]
    assert "job_type: matching_run_for_vacancy_v1" in fake_telegram.calls[0]["text"]
    assert "RuntimeError: boom" in fake_telegram.calls[0]["text"]


def test_send_error_alert_returns_false_when_not_configured(monkeypatch) -> None:
    fake_telegram = FakeTelegramBotClient()
    monkeypatch.setattr(
        "src.monitoring.telegram_alerts.get_settings",
        lambda: SimpleNamespace(
            app_env="test",
            telegram_bot_token="",
            telegram_error_chat_id=None,
        ),
    )

    service = TelegramErrorAlertService(telegram=fake_telegram)

    sent = service.send_error_alert(
        source="telegram_webhook",
        summary="Webhook failed.",
    )

    assert sent is False
    assert fake_telegram.calls == []
