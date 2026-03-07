from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Optional
from xml.etree import ElementTree
from zipfile import ZipFile

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.db.repositories.files import FilesRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.integrations.supabase_storage import SupabaseStorageClient
from src.integrations.telegram_bot import TelegramBotClient

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

logger = get_logger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    text: str
    mode: str
    source: str
    metadata: dict


class ContentIngestionService:
    def __init__(self, session):
        self.session = session
        self.settings = get_settings()
        self.files = FilesRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self._storage: Optional[SupabaseStorageClient] = None
        self._telegram: Optional[TelegramBotClient] = None
        self._openai = None

    def ingest_raw_message(self, raw_message) -> IngestionResult:
        existing_text = " ".join((raw_message.text_content or "").split()).strip()
        if existing_text:
            return IngestionResult(
                text=existing_text,
                mode="passthrough",
                source="raw_message",
                metadata={"content_type": raw_message.content_type},
            )
        if raw_message.file_id is None:
            raise ValueError("Raw message has neither text content nor file attachment.")
        file_row = self.files.get_by_id(raw_message.file_id)
        if file_row is None:
            raise ValueError("Attached file was not found for raw message ingestion.")
        return self.ingest_file(file_row)

    def ingest_candidate_version(self, version) -> IngestionResult:
        existing_text = " ".join((version.extracted_text or version.transcript_text or "").split()).strip()
        if existing_text:
            return IngestionResult(
                text=existing_text,
                mode="passthrough",
                source="candidate_profile_version",
                metadata={"source_type": version.source_type},
            )
        return self._ingest_version_source(
            source_file_id=version.source_file_id,
            source_raw_message_id=version.source_raw_message_id,
            source_type=version.source_type,
        )

    def ingest_vacancy_version(self, version) -> IngestionResult:
        existing_text = " ".join((version.extracted_text or version.transcript_text or "").split()).strip()
        if existing_text:
            return IngestionResult(
                text=existing_text,
                mode="passthrough",
                source="vacancy_version",
                metadata={"source_type": version.source_type},
            )
        return self._ingest_version_source(
            source_file_id=version.source_file_id,
            source_raw_message_id=version.source_raw_message_id,
            source_type=version.source_type,
        )

    def ingest_file(self, file_row) -> IngestionResult:
        kind = (file_row.kind or "").strip().lower()
        if kind == "document":
            return self._extract_document_text(file_row)
        if kind in {"voice", "video"}:
            return self._transcribe_media(file_row)
        raise ValueError(f"Unsupported file kind for ingestion: {file_row.kind}")

    def _ingest_version_source(self, *, source_file_id, source_raw_message_id, source_type: str) -> IngestionResult:
        if source_file_id is not None:
            file_row = self.files.get_by_id(source_file_id)
            if file_row is None:
                raise ValueError("Source file was not found for version ingestion.")
            return self.ingest_file(file_row)

        if source_raw_message_id is not None:
            raw_message = self.raw_messages.get_by_id(source_raw_message_id)
            if raw_message is None:
                raise ValueError("Source raw message was not found for version ingestion.")
            return self.ingest_raw_message(raw_message)

        raise ValueError(f"No raw source is available for {source_type}.")

    @property
    def storage(self) -> SupabaseStorageClient:
        if self._storage is None:
            self._storage = SupabaseStorageClient()
        return self._storage

    @property
    def telegram(self) -> TelegramBotClient:
        if self._telegram is None:
            self._telegram = TelegramBotClient()
        return self._telegram

    @property
    def openai(self):
        if self._openai is None:
            if not self.settings.openai_api_key or OpenAI is None:
                raise RuntimeError("OpenAI transcription client is not configured.")
            self._openai = OpenAI(api_key=self.settings.openai_api_key)
        return self._openai

    def _download_file_bytes(self, file_row) -> tuple[bytes, dict]:
        if file_row.storage_key:
            try:
                return self.storage.download_bytes(storage_key=file_row.storage_key), {
                    "download_source": "supabase_storage",
                    "storage_key": file_row.storage_key,
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ingestion_storage_download_failed",
                    file_id=str(file_row.id),
                    storage_key=file_row.storage_key,
                    error=str(exc),
                )

        if file_row.telegram_file_id:
            file_info = self.telegram.get_file(telegram_file_id=file_row.telegram_file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                raise ValueError("Telegram file path is missing.")
            return self.telegram.download_file_bytes(file_path=file_path), {
                "download_source": "telegram",
                "telegram_file_path": file_path,
            }

        raise ValueError("File is not available in storage and has no Telegram reference.")

    def _extract_document_text(self, file_row) -> IngestionResult:
        content, download_metadata = self._download_file_bytes(file_row)
        extension = (file_row.extension or "").strip().lower()
        mime_type = (file_row.mime_type or "").strip().lower()

        if extension == "txt" or mime_type.startswith("text/"):
            text = self._decode_text_bytes(content)
            return IngestionResult(
                text=text,
                mode="document_extract",
                source="document_text",
                metadata={**download_metadata, "parser": "plain_text", "extension": extension or None},
            )

        if extension == "pdf" or mime_type == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
            if not text:
                raise ValueError("PDF extraction produced empty text.")
            return IngestionResult(
                text=text,
                mode="document_extract",
                source="document_pdf",
                metadata={**download_metadata, "parser": "pypdf", "page_count": len(reader.pages)},
            )

        if extension == "docx" or mime_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }:
            text = self._extract_docx_text(content)
            if not text:
                raise ValueError("DOCX extraction produced empty text.")
            return IngestionResult(
                text=text,
                mode="document_extract",
                source="document_docx",
                metadata={**download_metadata, "parser": "docx-xml"},
            )

        raise ValueError(f"Unsupported document format: extension={extension!r} mime_type={mime_type!r}")

    def _transcribe_media(self, file_row) -> IngestionResult:
        content, download_metadata = self._download_file_bytes(file_row)
        extension = (file_row.extension or "").strip().lower() or ("ogg" if file_row.kind == "voice" else "mp4")
        mime_type = file_row.mime_type or "application/octet-stream"
        filename = f"{file_row.kind or 'media'}.{extension}"
        response = self.openai.audio.transcriptions.create(
            file=(filename, content, mime_type),
            model=self.settings.openai_model_transcription,
            response_format="verbose_json",
        )
        text = " ".join((getattr(response, "text", "") or "").split()).strip()
        if not text:
            raise ValueError("OpenAI transcription returned empty text.")
        return IngestionResult(
            text=text,
            mode="transcription",
            source="openai_audio",
            metadata={
                **download_metadata,
                "model_name": self.settings.openai_model_transcription,
                "file_kind": file_row.kind,
                "mime_type": mime_type,
                "extension": extension,
            },
        )

    def _decode_text_bytes(self, content: bytes) -> str:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                text = content.decode(encoding)
            except UnicodeDecodeError:
                continue
            normalized = text.strip()
            if normalized:
                return normalized
        raise ValueError("Text document could not be decoded.")

    def _extract_docx_text(self, content: bytes) -> str:
        with ZipFile(BytesIO(content)) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml_bytes)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            fragments = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            text = "".join(fragments).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs).strip()
