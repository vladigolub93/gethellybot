from types import SimpleNamespace
from uuid import uuid4

from src.ingestion.service import ContentIngestionService


class FakeSession:
    pass


def test_extract_document_text_from_txt_bytes(monkeypatch) -> None:
    service = ContentIngestionService(FakeSession())
    file_row = SimpleNamespace(
        id=uuid4(),
        kind="document",
        extension="txt",
        mime_type="text/plain",
        storage_key="telegram/test/sample.txt",
    )

    monkeypatch.setattr(
        service,
        "_download_file_bytes",
        lambda _file_row: (b"Senior Python engineer\nFastAPI, PostgreSQL", {"download_source": "test"}),
    )

    result = service.ingest_file(file_row)

    assert result.mode == "document_extract"
    assert result.source == "document_text"
    assert "Senior Python engineer" in result.text


def test_ingest_raw_message_prefers_existing_text() -> None:
    service = ContentIngestionService(FakeSession())
    raw_message = SimpleNamespace(
        text_content="  Already parsed text  ",
        file_id=None,
        content_type="text",
    )

    result = service.ingest_raw_message(raw_message)

    assert result.mode == "passthrough"
    assert result.text == "Already parsed text"


def test_transcribe_media_uses_json_for_gpt4o_transcribe_models(monkeypatch) -> None:
    service = ContentIngestionService(FakeSession())
    calls = []

    class _FakeTranscriptions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text="Warsaw", logprobs=[{"token": "Warsaw", "logprob": -0.01}])

    service.settings.openai_model_transcription = "gpt-4o-mini-transcribe"
    service._openai = SimpleNamespace(audio=SimpleNamespace(transcriptions=_FakeTranscriptions()))

    monkeypatch.setattr(
        service,
        "_download_file_bytes",
        lambda _file_row: (b"voice-bytes", {"download_source": "test"}),
    )

    file_row = SimpleNamespace(
        id=uuid4(),
        kind="voice",
        extension="ogg",
        mime_type="audio/ogg",
        provider_metadata={"duration": 3},
    )

    result = service.ingest_file(file_row, prompt_text="Warsaw")

    assert result.text == "Warsaw"
    assert calls[0]["response_format"] == "json"
    assert calls[0]["include"] == ["logprobs"]


def test_transcribe_media_keeps_verbose_json_for_non_gpt4o_models(monkeypatch) -> None:
    service = ContentIngestionService(FakeSession())
    calls = []

    class _FakeTranscriptions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text="Kyiv", duration=2, segments=[])

    service.settings.openai_model_transcription = "whisper-1"
    service._openai = SimpleNamespace(audio=SimpleNamespace(transcriptions=_FakeTranscriptions()))

    monkeypatch.setattr(
        service,
        "_download_file_bytes",
        lambda _file_row: (b"voice-bytes", {"download_source": "test"}),
    )

    file_row = SimpleNamespace(
        id=uuid4(),
        kind="voice",
        extension="ogg",
        mime_type="audio/ogg",
        provider_metadata={"duration": 2},
    )

    result = service.ingest_file(file_row, prompt_text="Kyiv")

    assert result.text == "Kyiv"
    assert calls[0]["response_format"] == "verbose_json"
    assert "include" not in calls[0]
