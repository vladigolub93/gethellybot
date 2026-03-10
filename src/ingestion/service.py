from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from statistics import mean
from typing import Any, Optional
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


@dataclass(frozen=True)
class ContentQualityError(ValueError):
    code: str
    user_message: str
    metadata: dict

    def __str__(self) -> str:
        return self.user_message


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

    def ingest_file(self, file_row, *, prompt_text: str | None = None) -> IngestionResult:
        kind = (file_row.kind or "").strip().lower()
        if kind == "document":
            return self._extract_document_text(file_row)
        if kind in {"voice", "video"}:
            return self._transcribe_media(file_row, prompt_text=prompt_text)
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
                metadata={
                    **download_metadata,
                    "parser": "plain_text",
                    "extension": extension or None,
                    "quality_status": "ok",
                },
            )

        if extension == "pdf" or mime_type == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
            text = "\n\n".join(part for part in page_texts if part).strip()
            page_count = len(reader.pages)
            text_length = len(text)
            avg_chars_per_page = round(text_length / max(page_count, 1), 2)
            if not text:
                raise ContentQualityError(
                    code="pdf_no_extractable_text",
                    user_message=(
                        "I saved the PDF, but it looks like a scanned or image-based file, so I couldn't pull reliable text from it. "
                        "Best move: send a text-based PDF/DOCX, paste the CV here, or send a short voice note."
                    ),
                    metadata={
                        **download_metadata,
                        "parser": "pypdf",
                        "page_count": page_count,
                        "text_length": text_length,
                        "avg_chars_per_page": avg_chars_per_page,
                        "quality_status": "retry_required",
                        "quality_reason": "pdf_no_extractable_text",
                    },
                )
            if self._looks_like_low_text_density_pdf(text_length=text_length, page_count=page_count):
                raise ContentQualityError(
                    code="pdf_low_text_density",
                    user_message=(
                        "I pulled only a tiny amount of text from that PDF, so it probably won't give a trustworthy summary. "
                        "If you can, send a text-based PDF/DOCX, paste the text here, or drop a quick voice note."
                    ),
                    metadata={
                        **download_metadata,
                        "parser": "pypdf",
                        "page_count": page_count,
                        "text_length": text_length,
                        "avg_chars_per_page": avg_chars_per_page,
                        "quality_status": "retry_required",
                        "quality_reason": "pdf_low_text_density",
                    },
                )
            return IngestionResult(
                text=text,
                mode="document_extract",
                source="document_pdf",
                metadata={
                    **download_metadata,
                    "parser": "pypdf",
                    "page_count": page_count,
                    "text_length": text_length,
                    "avg_chars_per_page": avg_chars_per_page,
                    "quality_status": "ok",
                },
            )

        if extension == "docx" or mime_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }:
            text = self._extract_docx_text(content)
            if not text:
                raise ContentQualityError(
                    code="docx_no_extractable_text",
                    user_message=(
                        "I saved the DOCX, but I couldn't pull readable text from it. "
                        "Try sending a clean DOCX/PDF, paste the text here, or send a short voice note."
                    ),
                    metadata={
                        **download_metadata,
                        "parser": "docx-xml",
                        "quality_status": "retry_required",
                        "quality_reason": "docx_no_extractable_text",
                    },
                )
            return IngestionResult(
                text=text,
                mode="document_extract",
                source="document_docx",
                metadata={
                    **download_metadata,
                    "parser": "docx-xml",
                    "text_length": len(text),
                    "quality_status": "ok",
                },
            )

        raise ValueError(f"Unsupported document format: extension={extension!r} mime_type={mime_type!r}")

    def _transcribe_media(self, file_row, *, prompt_text: str | None = None) -> IngestionResult:
        content, download_metadata = self._download_file_bytes(file_row)
        extension = (file_row.extension or "").strip().lower() or ("ogg" if file_row.kind == "voice" else "mp4")
        mime_type = file_row.mime_type or "application/octet-stream"
        filename = f"{file_row.kind or 'media'}.{extension}"
        model_name = self.settings.openai_model_transcription
        response_format = self._transcription_response_format(model_name)
        request_kwargs = {
            "file": (filename, content, mime_type),
            "model": model_name,
            "response_format": response_format,
        }
        if self._supports_transcription_logprobs(model_name, response_format):
            request_kwargs["include"] = ["logprobs"]
        if prompt_text:
            request_kwargs["prompt"] = prompt_text
        response = self.openai.audio.transcriptions.create(**request_kwargs)
        response_data = self._serialize_response(response)
        text = " ".join(
            (getattr(response, "text", None) or response_data.get("text") or "").split()
        ).strip()
        if not text:
            raise ContentQualityError(
                code="transcription_empty",
                user_message=(
                    "I saved the voice/video, but the transcript came back empty. "
                    "Please resend it as a cleaner voice note or just paste the key details in text."
                ),
                metadata={
                    **download_metadata,
                    "model_name": model_name,
                    "file_kind": file_row.kind,
                    "mime_type": mime_type,
                    "extension": extension,
                    "response_format": response_format,
                    "quality_status": "retry_required",
                    "quality_reason": "transcription_empty",
                },
            )
        quality_metadata = self._assess_transcription_quality(
            response=response,
            response_data=response_data,
            text=text,
            file_row=file_row,
        )
        if quality_metadata["quality_status"] != "ok":
            raise ContentQualityError(
                code=quality_metadata["quality_reason"],
                user_message=(
                    "I saved the voice/video, but the transcript looks too noisy to trust. "
                    "Best move: resend a cleaner recording or paste the same info in text."
                ),
                metadata={
                    **download_metadata,
                    "model_name": model_name,
                    "file_kind": file_row.kind,
                    "mime_type": mime_type,
                    "extension": extension,
                    "response_format": response_format,
                    "transcript_text": text,
                    **quality_metadata,
                },
            )
        return IngestionResult(
            text=text,
            mode="transcription",
            source="openai_audio",
            metadata={
                **download_metadata,
                "model_name": model_name,
                "file_kind": file_row.kind,
                "mime_type": mime_type,
                "extension": extension,
                "response_format": response_format,
                **quality_metadata,
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

    @staticmethod
    def _looks_like_low_text_density_pdf(*, text_length: int, page_count: int) -> bool:
        if page_count <= 0:
            return True
        if page_count == 1:
            return text_length < 80
        avg_chars_per_page = text_length / page_count
        return text_length < 200 or avg_chars_per_page < 80

    def _assess_transcription_quality(self, *, response: Any, response_data: dict, text: str, file_row) -> dict:
        duration = self._coerce_float(
            response_data.get("duration")
            or getattr(response, "duration", None)
            or ((getattr(file_row, "provider_metadata", None) or {}).get("duration"))
        )
        segments = response_data.get("segments") or getattr(response, "segments", None) or []
        logprobs = response_data.get("logprobs") or getattr(response, "logprobs", None) or []
        word_count = len(text.split())

        avg_logprob_values = [
            value
            for value in (
                self._coerce_float(self._segment_value(segment, "avg_logprob")) for segment in segments
            )
            if value is not None
        ]
        no_speech_prob_values = [
            value
            for value in (
                self._coerce_float(self._segment_value(segment, "no_speech_prob")) for segment in segments
            )
            if value is not None
        ]
        token_logprob_values = self._extract_logprob_values(logprobs)

        mean_avg_logprob = round(mean(avg_logprob_values), 4) if avg_logprob_values else None
        mean_no_speech_prob = round(mean(no_speech_prob_values), 4) if no_speech_prob_values else None
        mean_token_logprob = round(mean(token_logprob_values), 4) if token_logprob_values else None

        quality_reason = None
        if duration is not None and duration >= 12 and word_count < 5:
            quality_reason = "transcription_low_density"
        elif duration is not None and duration >= 8 and len(text) < 20:
            quality_reason = "transcription_low_density"
        elif mean_avg_logprob is not None and mean_avg_logprob <= -1.35 and word_count < 20:
            quality_reason = "transcription_low_confidence"
        elif mean_no_speech_prob is not None and mean_no_speech_prob >= 0.55 and word_count < 20:
            quality_reason = "transcription_high_no_speech"
        elif mean_token_logprob is not None and mean_token_logprob <= -1.35 and word_count < 20:
            quality_reason = "transcription_low_confidence"

        return {
            "duration_seconds": duration,
            "word_count": word_count,
            "segment_count": len(segments),
            "mean_avg_logprob": mean_avg_logprob,
            "mean_no_speech_prob": mean_no_speech_prob,
            "mean_token_logprob": mean_token_logprob,
            "quality_status": "retry_required" if quality_reason else "ok",
            "quality_reason": quality_reason,
        }

    @staticmethod
    def _transcription_response_format(model_name: str) -> str:
        normalized = (model_name or "").strip().lower()
        if normalized.startswith("gpt-4o") and "transcribe" in normalized:
            return "json"
        return "verbose_json"

    @staticmethod
    def _supports_transcription_logprobs(model_name: str, response_format: str) -> bool:
        normalized = (model_name or "").strip().lower()
        return response_format == "json" and normalized.startswith("gpt-4o") and "transcribe" in normalized

    @classmethod
    def _extract_logprob_values(cls, payload: Any) -> list[float]:
        values: list[float] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if "logprob" in node:
                    value = cls._coerce_float(node.get("logprob"))
                    if value is not None:
                        values.append(value)
                for item in node.values():
                    _walk(item)
                return
            if isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return values

    @staticmethod
    def _serialize_response(response: Any) -> dict:
        if hasattr(response, "model_dump"):
            try:
                return response.model_dump()
            except Exception:  # noqa: BLE001
                return {}
        if hasattr(response, "to_dict"):
            try:
                return response.to_dict()
            except Exception:  # noqa: BLE001
                return {}
        return {}

    @staticmethod
    def _segment_value(segment: Any, key: str):
        if isinstance(segment, dict):
            return segment.get(key)
        return getattr(segment, key, None)

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
