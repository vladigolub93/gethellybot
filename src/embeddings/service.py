from __future__ import annotations

from dataclasses import dataclass

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.embeddings.constants import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

logger = get_logger(__name__)


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model_name: str
    dimensions: int
    canonical_text: str


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key and OpenAI is not None)

    @property
    def dimensions(self) -> int:
        value = self.settings.openai_embedding_dimensions or DEFAULT_EMBEDDING_DIMENSIONS
        return int(value)

    @property
    def model_name(self) -> str:
        return (self.settings.openai_model_embeddings or DEFAULT_EMBEDDING_MODEL).strip()

    @property
    def client(self):
        if self._client is None:
            if not self.enabled:
                raise RuntimeError("OpenAI embeddings client is not configured.")
            self._client = OpenAI(api_key=self.settings.openai_api_key)
        return self._client

    def build_candidate_embedding(self, summary: dict) -> EmbeddingResult | None:
        canonical_text = self._candidate_canonical_text(summary)
        return self._embed_text(canonical_text)

    def build_vacancy_embedding(self, summary: dict, vacancy) -> EmbeddingResult | None:
        canonical_text = self._vacancy_canonical_text(summary, vacancy)
        return self._embed_text(canonical_text)

    def _embed_text(self, canonical_text: str) -> EmbeddingResult | None:
        if not canonical_text:
            return None
        if not self.enabled:
            return None
        response = self.client.embeddings.create(
            input=canonical_text,
            model=self.model_name,
            dimensions=self.dimensions,
            encoding_format="float",
        )
        item = (response.data or [None])[0]
        if item is None or not getattr(item, "embedding", None):
            raise RuntimeError("Embeddings API returned no embedding vector.")
        vector = [float(value) for value in item.embedding]
        return EmbeddingResult(
            vector=vector,
            model_name=self.model_name,
            dimensions=self.dimensions,
            canonical_text=canonical_text,
        )

    def safe_build_candidate_embedding(self, summary: dict) -> EmbeddingResult | None:
        try:
            return self.build_candidate_embedding(summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_embedding_failed", error=str(exc))
            return None

    def safe_build_vacancy_embedding(self, summary: dict, vacancy) -> EmbeddingResult | None:
        try:
            return self.build_vacancy_embedding(summary, vacancy)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_embedding_failed", error=str(exc))
            return None

    def _candidate_canonical_text(self, summary: dict) -> str:
        summary = summary or {}
        parts = [
            self._line("headline", summary.get("headline")),
            self._line("target_role", summary.get("target_role")),
            self._line("years_experience", summary.get("years_experience")),
            self._line("skills", ", ".join(summary.get("skills") or [])),
            self._line("experience_excerpt", summary.get("experience_excerpt")),
        ]
        return "\n".join(part for part in parts if part).strip()

    def _vacancy_canonical_text(self, summary: dict, vacancy) -> str:
        summary = summary or {}
        vacancy_skills = getattr(vacancy, "primary_tech_stack_json", None) or []
        parts = [
            self._line("role_title", summary.get("role_title") or getattr(vacancy, "role_title", None)),
            self._line(
                "seniority",
                summary.get("seniority_normalized") or getattr(vacancy, "seniority_normalized", None),
            ),
            self._line("tech_stack", ", ".join(summary.get("primary_tech_stack") or vacancy_skills)),
            self._line(
                "project_description",
                summary.get("project_description_excerpt") or getattr(vacancy, "project_description", None),
            ),
            self._line("required_skills", ", ".join(summary.get("required_skills") or [])),
        ]
        return "\n".join(part for part in parts if part).strip()

    def _line(self, key: str, value) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip()
        if not normalized:
            return None
        return f"{key}: {normalized}"
