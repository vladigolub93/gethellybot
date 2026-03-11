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
    assert normalized.chat_type == "private"
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


def test_normalize_document_message() -> None:
    update = {
        "update_id": 125,
        "message": {
            "message_id": 79,
            "chat": {"id": 557, "type": "private"},
            "from": {
                "id": 1001,
                "first_name": "Alex",
            },
            "document": {
                "file_id": "doc-1",
                "file_unique_id": "uniq-doc-1",
                "file_name": "resume.pdf",
                "mime_type": "application/pdf",
                "file_size": 1024,
            },
        },
    }

    normalized = normalize_telegram_update(update)

    assert normalized.content_type == "document"
    assert normalized.file is not None
    assert normalized.file.kind == "document"
    assert normalized.file.telegram_file_id == "doc-1"
    assert normalized.file.extension == "pdf"


def test_normalize_voice_message() -> None:
    update = {
        "update_id": 126,
        "message": {
            "message_id": 80,
            "chat": {"id": 558, "type": "private"},
            "from": {
                "id": 1002,
                "first_name": "Mila",
            },
            "voice": {
                "file_id": "voice-1",
                "file_unique_id": "uniq-voice-1",
                "mime_type": "audio/ogg",
                "file_size": 4096,
            },
        },
    }

    normalized = normalize_telegram_update(update)

    assert normalized.content_type == "voice"
    assert normalized.file is not None
    assert normalized.file.kind == "voice"
    assert normalized.file.telegram_file_id == "voice-1"
    assert normalized.file.extension == "ogg"
