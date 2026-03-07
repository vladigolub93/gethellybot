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
