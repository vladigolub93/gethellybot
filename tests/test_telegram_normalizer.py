from src.telegram.normalizer import normalize_telegram_update


def test_normalize_start_message() -> None:
    update = {
        "update_id": 123,
        "message": {
            "message_id": 77,
            "text": "/start",
            "chat": {"id": 555, "type": "private"},
            "from": {
                "id": 999,
                "first_name": "Vlad",
                "last_name": "Golub",
                "username": "vlad",
                "language_code": "en",
            },
        },
    }

    normalized = normalize_telegram_update(update)

    assert normalized.update_id == 123
    assert normalized.telegram_user_id == 999
    assert normalized.telegram_chat_id == 555
    assert normalized.content_type == "text"
    assert normalized.text == "/start"
    assert normalized.display_name == "Vlad Golub"


def test_normalize_contact_message() -> None:
    update = {
        "update_id": 124,
        "message": {
            "message_id": 78,
            "chat": {"id": 556, "type": "private"},
            "from": {
                "id": 1000,
                "first_name": "Jane",
            },
            "contact": {
                "phone_number": "+1234567890",
            },
        },
    }

    normalized = normalize_telegram_update(update)

    assert normalized.content_type == "contact"
    assert normalized.contact_phone_number == "+1234567890"
