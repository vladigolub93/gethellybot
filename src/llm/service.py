from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypeVar

from pydantic import BaseModel

from src.candidate_profile.question_parser import COUNTRY_CODES, parse_candidate_questions
from src.candidate_profile.summary_builder import build_candidate_summary
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.evaluation.scoring import evaluate_candidate
from src.interview.question_plan import build_question_plan
from src.llm.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    REASONING_SYSTEM_PROMPT,
    candidate_cv_prompt,
    candidate_questions_prompt,
    candidate_summary_edit_prompt,
    interview_evaluation_prompt,
    interview_question_plan_prompt,
    vacancy_clarifications_prompt,
    vacancy_jd_prompt,
)
from src.llm.schemas import (
    CandidateQuestionParseSchema,
    CandidateSummarySchema,
    InterviewEvaluationSchema,
    InterviewQuestionPlanSchema,
    VacancyClarificationSchema,
    VacancySummarySchema,
)
from src.vacancy.question_parser import parse_vacancy_clarifications
from src.vacancy.summary_builder import build_vacancy_summary

logger = get_logger(__name__)

try:
    from sqlalchemy.orm import Session as SASession
except Exception:  # pragma: no cover
    SASession = object

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMResult:
    payload: dict
    model_name: str
    prompt_version: str


class HellyLLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key and OpenAI is not None)

    def _client_instance(self):
        if self._client is None:
            if not self.enabled:
                raise RuntimeError("OpenAI client is not configured.")
            self._client = OpenAI(api_key=self.settings.openai_api_key)
        return self._client

    def _model_candidates(self, primary_model: str) -> list[str]:
        fallback_model = "gpt-5.2"
        models = [primary_model.strip() or "gpt-5.4"]
        if fallback_model not in models:
            models.append(fallback_model)
        return models

    def _is_model_unavailable_error(self, exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        text = str(exc).lower()
        if status_code not in {400, 404}:
            return False
        return "model" in text and (
            "not found" in text
            or "does not exist" in text
            or "unavailable" in text
            or "unsupported" in text
        )

    def parse(
        self,
        *,
        schema: type[T],
        system_prompt: str,
        user_prompt: str,
        primary_model: str,
        prompt_version: str,
    ) -> LLMResult:
        last_error = None
        for model_name in self._model_candidates(primary_model):
            try:
                response = self._client_instance().responses.parse(
                    model=model_name,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    text_format=schema,
                )
                parsed = getattr(response, "output_parsed", None)
                if parsed is None:
                    raise RuntimeError("OpenAI returned no parsed structured output.")
                return LLMResult(
                    payload=parsed.model_dump(exclude_none=True),
                    model_name=model_name,
                    prompt_version=prompt_version,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "llm_parse_failed",
                    prompt_version=prompt_version,
                    attempted_model=model_name,
                    error=str(exc),
                )
                if not self._is_model_unavailable_error(exc):
                    break
        raise RuntimeError(f"LLM call failed for {prompt_version}: {last_error}") from last_error


_client = HellyLLMClient()


def should_use_llm_runtime(session=None) -> bool:
    return isinstance(session, SASession) and _client.enabled


def _clean_text(value: Optional[str], *, limit: int) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None
    return normalized[:limit]


def _normalize_skill_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        item = " ".join((value or "").lower().split()).strip(" ,.")
        if item and item not in normalized:
            normalized.append(item)
    return normalized[:12]


def _normalize_work_format(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"remote", "hybrid", "office"}:
        return normalized
    if normalized in {"onsite", "on-site"}:
        return "office"
    return None


def _normalize_seniority(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"junior", "middle", "senior"}:
        return normalized
    if normalized in {"mid", "mid-level", "mid level"}:
        return "middle"
    if normalized in {"lead", "staff", "principal"}:
        return "senior"
    return None


def _normalize_currency(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().upper()
    if normalized in {"USD", "EUR", "GBP"}:
        return normalized
    return None


def _normalize_period(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"month", "year"}:
        return normalized
    if normalized in {"monthly"}:
        return "month"
    if normalized in {"annual", "annually", "yearly"}:
        return "year"
    return None


def _normalize_country_codes(values: list[str]) -> list[str]:
    allowed = set(COUNTRY_CODES.values())
    normalized: list[str] = []
    for value in values or []:
        item = (value or "").strip().upper()
        if item in allowed and item not in normalized:
            normalized.append(item)
    return normalized


def extract_candidate_summary_with_llm(source_text: str, source_type: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateSummarySchema,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=candidate_cv_prompt(source_text, source_type),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="candidate_cv_extract_llm_v1",
    )
    summary = {
        "status": "draft",
        "source_type": source_type,
        "headline": _clean_text(result.payload.get("headline"), limit=180),
        "experience_excerpt": _clean_text(
            result.payload.get("experience_excerpt") or source_text,
            limit=1200,
        ),
        "years_experience": result.payload.get("years_experience"),
        "skills": _normalize_skill_list(result.payload.get("skills") or []),
    }
    return LLMResult(
        payload={key: value for key, value in summary.items() if value not in (None, [])},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def merge_candidate_summary_with_llm(base_summary: dict, edit_request_text: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateSummarySchema,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=candidate_summary_edit_prompt(base_summary, edit_request_text),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="candidate_summary_edit_apply_llm_v1",
    )
    merged = dict(base_summary or {})
    merged.update(
        {
            "status": "draft",
            "headline": _clean_text(result.payload.get("headline") or merged.get("headline"), limit=180),
            "experience_excerpt": _clean_text(
                result.payload.get("experience_excerpt") or merged.get("experience_excerpt"),
                limit=1200,
            ),
            "years_experience": result.payload.get(
                "years_experience",
                merged.get("years_experience"),
            ),
            "skills": _normalize_skill_list(
                result.payload.get("skills") or merged.get("skills") or []
            ),
            "candidate_edit_notes": _clean_text(edit_request_text, limit=500),
        }
    )
    return LLMResult(
        payload={key: value for key, value in merged.items() if value not in (None, [])},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def parse_candidate_questions_with_llm(text: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateQuestionParseSchema,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=candidate_questions_prompt(text),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="candidate_questions_parse_llm_v1",
    )
    payload = {
        "salary_min": result.payload.get("salary_min"),
        "salary_max": result.payload.get("salary_max"),
        "salary_currency": _normalize_currency(result.payload.get("salary_currency")),
        "salary_period": _normalize_period(result.payload.get("salary_period")),
        "location_text": _clean_text(result.payload.get("location_text"), limit=160),
        "city": _clean_text(result.payload.get("city"), limit=80),
        "country_code": (result.payload.get("country_code") or "").strip().upper() or None,
        "work_format": _normalize_work_format(result.payload.get("work_format")),
    }
    if payload["country_code"] not in set(COUNTRY_CODES.values()):
        payload["country_code"] = None
    return LLMResult(
        payload={key: value for key, value in payload.items() if value is not None},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def extract_vacancy_summary_with_llm(source_text: str, source_type: str) -> LLMResult:
    result = _client.parse(
        schema=VacancySummarySchema,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=vacancy_jd_prompt(source_text, source_type),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="vacancy_jd_extract_llm_v1",
    )
    summary = {
        "status": "draft",
        "source_type": source_type,
        "role_title": _clean_text(result.payload.get("role_title"), limit=120),
        "seniority_normalized": _normalize_seniority(result.payload.get("seniority_normalized")),
        "primary_tech_stack": _normalize_skill_list(result.payload.get("primary_tech_stack") or []),
        "project_description_excerpt": _clean_text(
            result.payload.get("project_description_excerpt") or source_text,
            limit=1200,
        ),
    }
    inconsistency_json = {"issues": result.payload.get("inconsistency_issues") or []}
    return LLMResult(
        payload={
            "summary": {key: value for key, value in summary.items() if value not in (None, [])},
            "inconsistency_json": inconsistency_json,
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def parse_vacancy_clarifications_with_llm(text: str) -> LLMResult:
    result = _client.parse(
        schema=VacancyClarificationSchema,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=vacancy_clarifications_prompt(text),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="vacancy_clarification_parse_llm_v1",
    )
    payload = {
        "role_title": _clean_text(result.payload.get("role_title"), limit=120),
        "seniority_normalized": _normalize_seniority(result.payload.get("seniority_normalized")),
        "budget_min": result.payload.get("budget_min"),
        "budget_max": result.payload.get("budget_max"),
        "budget_currency": _normalize_currency(result.payload.get("budget_currency")),
        "budget_period": _normalize_period(result.payload.get("budget_period")),
        "countries_allowed_json": _normalize_country_codes(
            result.payload.get("countries_allowed_json") or []
        ),
        "work_format": _normalize_work_format(result.payload.get("work_format")),
        "team_size": result.payload.get("team_size"),
        "project_description": _clean_text(result.payload.get("project_description"), limit=1200),
        "primary_tech_stack_json": _normalize_skill_list(
            result.payload.get("primary_tech_stack_json") or []
        ),
    }
    return LLMResult(
        payload={
            key: value
            for key, value in payload.items()
            if value not in (None, []) and value != ""
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_interview_question_plan_with_llm(vacancy, candidate_summary: dict) -> LLMResult:
    vacancy_context = {
        "role_title": getattr(vacancy, "role_title", None),
        "seniority_normalized": getattr(vacancy, "seniority_normalized", None),
        "primary_tech_stack_json": getattr(vacancy, "primary_tech_stack_json", None),
        "project_description": getattr(vacancy, "project_description", None),
    }
    result = _client.parse(
        schema=InterviewQuestionPlanSchema,
        system_prompt=REASONING_SYSTEM_PROMPT,
        user_prompt=interview_question_plan_prompt(vacancy_context, candidate_summary),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_question_plan_llm_v1",
    )
    questions = [
        _clean_text(question, limit=220)
        for question in (result.payload.get("questions") or [])
        if _clean_text(question, limit=220)
    ]
    return LLMResult(
        payload={"questions": questions[:7]},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def evaluate_candidate_with_llm(candidate_summary: dict, vacancy, answer_texts: list[str]) -> LLMResult:
    vacancy_context = {
        "role_title": getattr(vacancy, "role_title", None),
        "seniority_normalized": getattr(vacancy, "seniority_normalized", None),
        "primary_tech_stack_json": getattr(vacancy, "primary_tech_stack_json", None),
        "project_description": getattr(vacancy, "project_description", None),
        "budget_min": getattr(vacancy, "budget_min", None),
        "budget_max": getattr(vacancy, "budget_max", None),
        "work_format": getattr(vacancy, "work_format", None),
    }
    result = _client.parse(
        schema=InterviewEvaluationSchema,
        system_prompt=REASONING_SYSTEM_PROMPT,
        user_prompt=interview_evaluation_prompt(candidate_summary, vacancy_context, answer_texts),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_evaluation_llm_v1",
    )
    score = result.payload.get("final_score")
    if score is None:
        score = 0.0
    score = max(0.0, min(1.0, float(score)))
    payload = {
        "final_score": round(score, 4),
        "strengths": result.payload.get("strengths") or [],
        "risks": result.payload.get("risks") or [],
        "recommendation": "advance"
        if str(result.payload.get("recommendation", "")).lower() == "advance"
        else "reject",
        "interview_summary": _clean_text(result.payload.get("interview_summary"), limit=1500)
        or "",
    }
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def safe_extract_candidate_summary(session, source_text: str, source_type: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return extract_candidate_summary_with_llm(source_text, source_type)
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_summary_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload=build_candidate_summary(source_text, source_type),
        model_name="baseline-deterministic",
        prompt_version="baseline_cv_extract_v1",
    )


def safe_merge_candidate_summary(session, base_summary: dict, edit_request_text: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return merge_candidate_summary_with_llm(base_summary, edit_request_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_summary_edit_fallback_to_baseline", error=str(exc))
    merged = dict(base_summary or {})
    merged["candidate_edit_notes"] = edit_request_text
    merged["status"] = "draft"
    return LLMResult(
        payload=merged,
        model_name="baseline-deterministic",
        prompt_version="baseline_summary_edit_apply_v1",
    )


def safe_parse_candidate_questions(session, text: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return parse_candidate_questions_with_llm(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_questions_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload=parse_candidate_questions(text),
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_questions_parse_v1",
    )


def safe_extract_vacancy_summary(session, source_text: str, source_type: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return extract_vacancy_summary_with_llm(source_text, source_type)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_summary_fallback_to_baseline", error=str(exc))
    summary, inconsistency_json = build_vacancy_summary(source_text, source_type)
    return LLMResult(
        payload={"summary": summary, "inconsistency_json": inconsistency_json},
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_jd_extract_v1",
    )


def safe_parse_vacancy_clarifications(session, text: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return parse_vacancy_clarifications_with_llm(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_clarification_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload=parse_vacancy_clarifications(text),
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_clarification_parse_v1",
    )


def safe_build_interview_question_plan(session, vacancy, candidate_summary: dict) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            result = build_interview_question_plan_with_llm(vacancy, candidate_summary)
            questions = result.payload.get("questions") or []
            if len(questions) >= 5:
                return result
            raise RuntimeError("LLM returned too few interview questions.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_plan_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload={"questions": build_question_plan(vacancy=vacancy, candidate_summary=candidate_summary)},
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_question_plan_v1",
    )


def safe_evaluate_candidate(session, candidate_summary: dict, vacancy, answer_texts: list[str]) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return evaluate_candidate_with_llm(candidate_summary, vacancy, answer_texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_evaluation_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload=evaluate_candidate(
            candidate_summary=candidate_summary,
            vacancy=vacancy,
            answer_texts=answer_texts,
        ),
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_evaluation_v1",
    )
