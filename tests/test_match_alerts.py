from types import SimpleNamespace
from uuid import uuid4

from src.monitoring.match_alerts import TelegramMatchAlertService


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


def test_send_match_alert_includes_admin_link_and_cv_name(monkeypatch) -> None:
    fake_telegram = FakeTelegramBotClient()
    match_id = uuid4()
    monkeypatch.setattr(
        "src.monitoring.match_alerts.get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="token",
            telegram_error_chat_id=-100777,
            app_base_url="https://helly.example.com",
        ),
    )

    service = TelegramMatchAlertService(telegram=fake_telegram)

    sent = service.send_match_alert(
        event_type="match_created",
        match=SimpleNamespace(id=match_id, status="shortlisted"),
        vacancy=SimpleNamespace(role_title="Node.js Developer"),
        candidate_profile=SimpleNamespace(id=uuid4()),
        candidate_version=SimpleNamespace(
            summary_json={"approval_summary_text": "You are Milana Trofimova, a Senior Backend Engineer."}
        ),
        candidate_user=SimpleNamespace(display_name="telegram junk"),
        manager_user=SimpleNamespace(display_name="Hiring Manager"),
        note="Shortlisted after rerank.",
    )

    assert sent is True
    assert fake_telegram.calls[0]["chat_id"] == -100777
    assert "event: match_created" in fake_telegram.calls[0]["text"]
    assert "candidate: Milana Trofimova" in fake_telegram.calls[0]["text"]
    assert f"link: https://helly.example.com/admin#/matches/{match_id}" in fake_telegram.calls[0]["text"]


def test_send_match_alert_returns_false_when_not_configured(monkeypatch) -> None:
    fake_telegram = FakeTelegramBotClient()
    monkeypatch.setattr(
        "src.monitoring.match_alerts.get_settings",
        lambda: SimpleNamespace(
            telegram_bot_token="",
            telegram_error_chat_id=None,
            app_base_url="https://helly.example.com",
        ),
    )

    service = TelegramMatchAlertService(telegram=fake_telegram)

    sent = service.send_match_alert(
        event_type="match_successful",
        match=SimpleNamespace(id=uuid4(), status="approved"),
    )

    assert sent is False
    assert fake_telegram.calls == []
