from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypeVar

from pydantic import BaseModel

from src.candidate_profile.question_parser import COUNTRY_CODES, parse_candidate_questions
from src.candidate_profile.summary_builder import build_approval_summary_text, build_candidate_summary
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.evaluation.scoring import evaluate_candidate
from src.interview.question_plan import build_question_plan
from src.llm.assets import build_user_facing_grounded_system_prompt, load_system_prompt
from src.llm.prompts import (
    STATE_ASSISTANCE_SYSTEM_PROMPT,
    bot_controller_prompt,
    candidate_rerank_prompt,
    candidate_cv_prompt,
    candidate_questions_prompt,
    candidate_summary_review_decision_prompt,
    candidate_summary_edit_prompt,
    deletion_confirmation_prompt,
    interview_invitation_copy_prompt,
    interview_answer_parse_prompt,
    interview_evaluation_prompt,
    interview_followup_decision_prompt,
    interview_question_plan_prompt,
    interview_session_conductor_prompt,
    recovery_prompt,
    response_copywriter_prompt,
    role_selection_prompt,
    small_talk_prompt,
    vacancy_clarifications_prompt,
    vacancy_inconsistency_detect_prompt,
    vacancy_jd_prompt,
    vacancy_summary_review_decision_prompt,
    vacancy_summary_edit_prompt,
)
from src.llm.state_assistance import state_assistance_prompt
from src.llm.schemas import (
    BotControllerDecisionSchema,
    CandidateRerankSchema,
    CandidateQuestionParseSchema,
    CandidateSummaryReviewDecisionSchema,
    CandidateSummarySchema,
    DeletionConfirmationSchema,
    InterviewAnswerParseSchema,
    InterviewEvaluationSchema,
    InterviewFollowupDecisionSchema,
    InterviewQuestionPlanSchema,
    InterviewSessionConductorTurnSchema,
    ResponseCopywriterSchema,
    StateAssistanceDecisionSchema,
    VacancyInconsistencySchema,
    VacancyClarificationSchema,
    VacancySummaryReviewDecisionSchema,
    VacancySummarySchema,
)
from src.shared.text import normalize_command_text
from src.vacancy.question_parser import parse_vacancy_clarifications
from src.vacancy.summary_builder import (
    build_vacancy_approval_summary_text,
    build_vacancy_summary,
)

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


def _vacancy_context(vacancy) -> dict:
    return {
        "role_title": getattr(vacancy, "role_title", None),
        "seniority_normalized": getattr(vacancy, "seniority_normalized", None),
        "primary_tech_stack_json": getattr(vacancy, "primary_tech_stack_json", None),
        "project_description": getattr(vacancy, "project_description", None),
        "budget_min": getattr(vacancy, "budget_min", None),
        "budget_max": getattr(vacancy, "budget_max", None),
        "work_format": getattr(vacancy, "work_format", None),
    }


def _fallback_interview_question_plan(vacancy, candidate_summary: dict) -> dict:
    baseline_questions = build_question_plan(vacancy=vacancy, candidate_summary=candidate_summary)[:4]
    default_types = ["behavioral", "situational", "role_specific", "motivation"]
    return {
        "questions": [
            {"id": index, "type": default_types[index - 1], "question": question}
            for index, question in enumerate(baseline_questions, start=1)
        ],
        "fallback_used": True,
    }


def _normalize_question_type(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"behavioral", "situational", "role_specific", "motivation"}:
        return normalized
    return None


def _normalize_answer_quality(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"strong", "mixed", "weak"}:
        return normalized
    return None


def _normalize_followup_reason(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if normalized in {"deepen", "clarify", "verify", "none"}:
        return normalized
    return None


def _normalize_inconsistency_findings(findings: list[dict]) -> list[dict]:
    normalized = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        severity = (item.get("severity") or "").strip().lower()
        category = (item.get("category") or "").strip().lower()
        finding = _clean_text(item.get("finding"), limit=240)
        if severity not in {"low", "medium", "high"}:
            continue
        if category not in {
            "stack_conflict",
            "seniority_conflict",
            "work_format_conflict",
            "scope_ambiguity",
            "other",
        }:
            continue
        if not finding:
            continue
        normalized.append(
            {
                "severity": severity,
                "category": category,
                "finding": finding,
            }
        )
    return normalized[:12]


def extract_candidate_summary_with_llm(source_text: str, source_type: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateSummarySchema,
        system_prompt=load_system_prompt("candidate", "cv_extract"),
        user_prompt=candidate_cv_prompt(source_text, source_type),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="candidate_cv_extract_llm_v2",
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
        "approval_summary_text": _clean_text(
            result.payload.get("approval_summary_text"),
            limit=500,
        ),
    }
    if not summary["approval_summary_text"]:
        summary["approval_summary_text"] = _clean_text(
            build_approval_summary_text(
                headline=summary["headline"] or "software professional",
                source_text=source_text,
                years_experience=summary["years_experience"],
                skills=summary["skills"],
            ),
            limit=500,
        )
    return LLMResult(
        payload={key: value for key, value in summary.items() if value not in (None, [])},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def merge_candidate_summary_with_llm(base_summary: dict, edit_request_text: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateSummarySchema,
        system_prompt=load_system_prompt("candidate", "summary_merge"),
        user_prompt=candidate_summary_edit_prompt(base_summary, edit_request_text),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="candidate_summary_edit_apply_llm_v2",
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
            "approval_summary_text": _clean_text(
                result.payload.get("approval_summary_text")
                or merged.get("approval_summary_text"),
                limit=500,
            ),
            "candidate_edit_notes": _clean_text(edit_request_text, limit=500),
        }
    )
    if not merged.get("approval_summary_text"):
        merged["approval_summary_text"] = _clean_text(
            build_approval_summary_text(
                headline=merged.get("headline") or "software professional",
                source_text=merged.get("experience_excerpt") or "",
                years_experience=merged.get("years_experience"),
                skills=merged.get("skills") or [],
            ),
            limit=500,
        )
    return LLMResult(
        payload={key: value for key, value in merged.items() if value not in (None, [])},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_summary_review_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateSummaryReviewDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt(
            "candidate",
            "summary_review_decision",
        ),
        user_prompt=candidate_summary_review_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_summary_review_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "approve_summary", "request_summary_change"}:
        proposed_action = None
    intent = _clean_text(result.payload.get("intent"), limit=80) or "help"
    response_text = _clean_text(result.payload.get("response_text"), limit=400)
    edit_text = _clean_text(result.payload.get("edit_text"), limit=500)
    if proposed_action == "request_summary_change" and not edit_text:
        proposed_action = None
        intent = "needs_clarification"
    return LLMResult(
        payload={
            "intent": intent,
            "response_text": response_text,
            "proposed_action": proposed_action,
            "edit_text": edit_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def parse_candidate_questions_with_llm(text: str) -> LLMResult:
    result = _client.parse(
        schema=CandidateQuestionParseSchema,
        system_prompt=load_system_prompt("candidate", "mandatory_field_parse"),
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
        system_prompt=load_system_prompt("vacancy", "jd_extract"),
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
        "approval_summary_text": _clean_text(
            result.payload.get("approval_summary_text"),
            limit=600,
        ),
    }
    if not summary["approval_summary_text"]:
        summary["approval_summary_text"] = _clean_text(
            build_vacancy_approval_summary_text(
                role_title=summary["role_title"],
                seniority_normalized=summary["seniority_normalized"],
                primary_tech_stack=summary["primary_tech_stack"],
                project_description_excerpt=summary["project_description_excerpt"],
                source_text=source_text,
            ),
            limit=600,
        )
    inconsistency_json = {"issues": result.payload.get("inconsistency_issues") or []}
    return LLMResult(
        payload={
            "summary": {key: value for key, value in summary.items() if value not in (None, [])},
            "inconsistency_json": inconsistency_json,
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def merge_vacancy_summary_with_llm(base_summary: dict, edit_request_text: str) -> LLMResult:
    result = _client.parse(
        schema=VacancySummarySchema,
        system_prompt=load_system_prompt("vacancy", "summary_merge"),
        user_prompt=vacancy_summary_edit_prompt(base_summary, edit_request_text),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="vacancy_summary_edit_apply_llm_v1",
    )
    merged = dict(base_summary or {})
    merged.update(
        {
            "status": "draft",
            "role_title": _clean_text(result.payload.get("role_title") or merged.get("role_title"), limit=120),
            "seniority_normalized": _normalize_seniority(
                result.payload.get("seniority_normalized") or merged.get("seniority_normalized")
            ),
            "primary_tech_stack": _normalize_skill_list(
                result.payload.get("primary_tech_stack") or merged.get("primary_tech_stack") or []
            ),
            "project_description_excerpt": _clean_text(
                result.payload.get("project_description_excerpt")
                or merged.get("project_description_excerpt"),
                limit=1200,
            ),
            "approval_summary_text": _clean_text(
                result.payload.get("approval_summary_text")
                or merged.get("approval_summary_text"),
                limit=600,
            ),
            "manager_edit_notes": _clean_text(edit_request_text, limit=500),
        }
    )
    if not merged.get("approval_summary_text"):
        merged["approval_summary_text"] = _clean_text(
            build_vacancy_approval_summary_text(
                role_title=merged.get("role_title"),
                seniority_normalized=merged.get("seniority_normalized"),
                primary_tech_stack=merged.get("primary_tech_stack") or [],
                project_description_excerpt=merged.get("project_description_excerpt"),
                source_text=merged.get("project_description_excerpt") or "",
            ),
            limit=600,
        )
    return LLMResult(
        payload={key: value for key, value in merged.items() if value not in (None, [])},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def vacancy_summary_review_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=VacancySummaryReviewDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("vacancy", "summary_review_decision"),
        user_prompt=vacancy_summary_review_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_summary_review_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "approve_summary", "request_summary_change"}:
        proposed_action = None
    intent = _clean_text(result.payload.get("intent"), limit=80) or "help"
    response_text = _clean_text(result.payload.get("response_text"), limit=400)
    edit_text = _clean_text(result.payload.get("edit_text"), limit=500)
    if proposed_action == "request_summary_change" and not edit_text:
        proposed_action = None
        intent = "needs_clarification"
    return LLMResult(
        payload={
            "intent": intent,
            "response_text": response_text,
            "proposed_action": proposed_action,
            "edit_text": edit_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def parse_vacancy_clarifications_with_llm(text: str) -> LLMResult:
    result = _client.parse(
        schema=VacancyClarificationSchema,
        system_prompt=load_system_prompt("vacancy", "clarification_parse"),
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


def build_interview_question_plan_with_llm(vacancy, candidate_summary: dict, cv_text: str | None = None) -> LLMResult:
    vacancy_context = _vacancy_context(vacancy)
    result = _client.parse(
        schema=InterviewQuestionPlanSchema,
        system_prompt=load_system_prompt("interview", "question_plan"),
        user_prompt=interview_question_plan_prompt(vacancy_context, candidate_summary, cv_text),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_question_plan_llm_v2",
    )
    questions = []
    for item in (result.payload.get("questions") or []):
        if not isinstance(item, dict):
            continue
        question_text = _clean_text(item.get("question"), limit=260)
        question_kind = (item.get("type") or "").strip().lower()
        question_id = item.get("id")
        if not question_text:
            continue
        if question_kind not in {"behavioral", "situational", "role_specific", "motivation"}:
            continue
        questions.append(
            {
                "id": int(question_id) if isinstance(question_id, int) else len(questions) + 1,
                "type": question_kind,
                "question": question_text,
            }
        )
    return LLMResult(
        payload={
            "questions": questions[:4],
            "fallback_used": bool(result.payload.get("fallback_used", False)),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def evaluate_candidate_with_llm(candidate_summary: dict, vacancy, answer_texts: list[str]) -> LLMResult:
    vacancy_context = _vacancy_context(vacancy)
    result = _client.parse(
        schema=InterviewEvaluationSchema,
        system_prompt=load_system_prompt("evaluation", "candidate_evaluate"),
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


def parse_interview_answer_with_llm(
    *,
    question_text: str,
    candidate_answer: str,
    candidate_summary: dict | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=InterviewAnswerParseSchema,
        system_prompt=load_system_prompt("interview", "answer_parse"),
        user_prompt=interview_answer_parse_prompt(
            question_text=question_text,
            candidate_answer=candidate_answer,
            candidate_summary=candidate_summary,
        ),
        primary_model=get_settings().openai_model_extraction,
        prompt_version="interview_answer_parse_llm_v1",
    )
    payload = {
        "answer_summary": _clean_text(result.payload.get("answer_summary"), limit=500) or "",
        "technologies": _normalize_skill_list(result.payload.get("technologies") or []),
        "systems_or_projects": [
            _clean_text(value, limit=120)
            for value in (result.payload.get("systems_or_projects") or [])
            if _clean_text(value, limit=120)
        ][:8],
        "ownership_level": (result.payload.get("ownership_level") or "weak").strip().lower(),
        "is_concrete": bool(result.payload.get("is_concrete")),
        "possible_profile_conflict": bool(result.payload.get("possible_profile_conflict")),
    }
    if payload["ownership_level"] not in {"strong", "mixed", "weak"}:
        payload["ownership_level"] = "weak"
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def decide_interview_followup_with_llm(
    *,
    question_text: str,
    question_kind: str,
    candidate_answer: str,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    follow_up_already_used: bool,
    answer_parse: dict | None,
) -> LLMResult:
    result = _client.parse(
        schema=InterviewFollowupDecisionSchema,
        system_prompt=load_system_prompt("interview", "followup_decision"),
        user_prompt=interview_followup_decision_prompt(
            question_text=question_text,
            question_kind=question_kind,
            candidate_answer=candidate_answer,
            candidate_summary=candidate_summary,
            vacancy_context=vacancy_context,
            follow_up_already_used=follow_up_already_used,
            answer_parse=answer_parse,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_followup_decision_llm_v1",
    )
    followup_reason = (result.payload.get("followup_reason") or "none").strip().lower()
    if followup_reason not in {"deepen", "clarify", "verify", "none"}:
        followup_reason = "none"
    payload = {
        "answer_quality": (result.payload.get("answer_quality") or "weak").strip().lower(),
        "ask_followup": bool(result.payload.get("ask_followup")) and not follow_up_already_used,
        "followup_reason": followup_reason,
        "followup_question": _clean_text(result.payload.get("followup_question"), limit=220),
    }
    if payload["answer_quality"] not in {"strong", "mixed", "weak"}:
        payload["answer_quality"] = "weak"
    if not payload["ask_followup"]:
        payload["followup_reason"] = "none"
        payload["followup_question"] = None
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def bot_controller_decision_with_llm(
    *,
    role: str | None,
    state: str | None,
    state_goal: str | None,
    allowed_actions: list[str],
    blocked_actions: list[str] | None,
    missing_requirements: list[str] | None,
    current_step_guidance: str | None,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=BotControllerDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("orchestrator", "bot_controller"),
        user_prompt=bot_controller_prompt(
            role=role,
            state=state,
            state_goal=state_goal,
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            missing_requirements=missing_requirements,
            current_step_guidance=current_step_guidance,
            latest_user_message=latest_user_message,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="bot_controller_llm_v2",
    )
    payload = {
        "intent": (result.payload.get("intent") or "unknown").strip().lower(),
        "tone": (result.payload.get("tone") or "neutral").strip().lower(),
        "response_mode": (result.payload.get("response_mode") or "recover").strip().lower(),
        "keep_current_state": bool(result.payload.get("keep_current_state", True)),
        "proposed_action": _clean_text(result.payload.get("proposed_action"), limit=120),
        "response_text": _clean_text(result.payload.get("response_text"), limit=500),
        "reason_code": result.payload.get("reason_code"),
    }
    if payload["intent"] not in {
        "on_flow_input",
        "small_talk",
        "support_request",
        "clarification_request",
        "off_topic",
        "destructive_intent",
        "unknown",
    }:
        payload["intent"] = "unknown"
    if payload["tone"] not in {"neutral", "friendly", "supportive", "firm"}:
        payload["tone"] = "neutral"
    if payload["response_mode"] not in {"answer", "recover", "clarify", "redirect"}:
        payload["response_mode"] = "recover"
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def state_assistance_decision_with_llm(
    *,
    state_prompt_slug: str,
    context,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=StateAssistanceDecisionSchema,
        system_prompt="\n\n".join(
            [
                STATE_ASSISTANCE_SYSTEM_PROMPT.strip(),
                build_user_facing_grounded_system_prompt("orchestrator", "state_assistance", state_prompt_slug),
            ]
        ),
        user_prompt=state_assistance_prompt(
            context=context,
            latest_user_message=latest_user_message,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version=f"state_assistance_{state_prompt_slug}_llm_v1",
    )
    payload = {
        "response_text": _clean_text(result.payload.get("response_text"), limit=500) or "",
        "intent": (result.payload.get("intent") or "support_request").strip().lower(),
        "keep_current_state": bool(result.payload.get("keep_current_state", True)),
        "suggested_action": _clean_text(result.payload.get("suggested_action"), limit=120),
        "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
    }
    if payload["intent"] not in {
        "support_request",
        "clarification_request",
        "constraint_report",
        "small_talk",
        "unknown",
    }:
        payload["intent"] = "unknown"
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def conduct_interview_turn_with_llm(
    *,
    mode: str,
    candidate_first_name: str | None,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    interview_plan: list[dict] | None,
    current_question: dict | None,
    candidate_answer: str | None,
    answer_quality: str | None,
    follow_up_used: bool,
    follow_up_reason: str | None,
) -> LLMResult:
    result = _client.parse(
        schema=InterviewSessionConductorTurnSchema,
        system_prompt=build_user_facing_grounded_system_prompt("interview", "session_conductor"),
        user_prompt=interview_session_conductor_prompt(
            mode=mode,
            candidate_first_name=candidate_first_name,
            candidate_summary=candidate_summary,
            vacancy_context=vacancy_context,
            interview_plan=interview_plan,
            current_question=current_question,
            candidate_answer=candidate_answer,
            answer_quality=answer_quality,
            follow_up_used=follow_up_used,
            follow_up_reason=follow_up_reason,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_session_conductor_llm_v1",
    )
    payload = {
        "mode": (result.payload.get("mode") or mode).strip().lower(),
        "utterance": _clean_text(result.payload.get("utterance"), limit=500) or "",
        "current_question_id": result.payload.get("current_question_id"),
        "current_question_type": _normalize_question_type(result.payload.get("current_question_type")),
        "answer_quality": _normalize_answer_quality(result.payload.get("answer_quality")),
        "follow_up_used": bool(result.payload.get("follow_up_used")),
        "follow_up_reason": _normalize_followup_reason(result.payload.get("follow_up_reason")),
        "move_to_next_question": bool(result.payload.get("move_to_next_question")),
        "interview_complete": bool(result.payload.get("interview_complete")),
    }
    return LLMResult(
        payload=payload,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def rerank_candidates_with_llm(*, vacancy, shortlisted_candidates: list[dict]) -> LLMResult:
    result = _client.parse(
        schema=CandidateRerankSchema,
        system_prompt=load_system_prompt("matching", "candidate_rerank"),
        user_prompt=candidate_rerank_prompt(
            vacancy_context=_vacancy_context(vacancy),
            shortlisted_candidates=shortlisted_candidates,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="matching_candidate_rerank_llm_v1",
    )
    ranked_candidates = []
    for item in result.payload.get("ranked_candidates") or []:
        if not isinstance(item, dict):
            continue
        candidate_ref = _clean_text(item.get("candidate_ref"), limit=120)
        rationale = _clean_text(item.get("rationale"), limit=280)
        rank = item.get("rank")
        fit_score = item.get("fit_score")
        if not candidate_ref or rationale is None:
            continue
        try:
            rank_value = int(rank)
            fit_score_value = max(0.0, min(1.0, float(fit_score)))
        except (TypeError, ValueError):
            continue
        ranked_candidates.append(
            {
                "candidate_ref": candidate_ref,
                "rank": rank_value,
                "fit_score": round(fit_score_value, 4),
                "rationale": rationale,
            }
        )
    ranked_candidates.sort(key=lambda item: item["rank"])
    return LLMResult(
        payload={"ranked_candidates": ranked_candidates},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def detect_vacancy_inconsistencies_with_llm(*, source_text: str, summary: dict) -> LLMResult:
    result = _client.parse(
        schema=VacancyInconsistencySchema,
        system_prompt=load_system_prompt("vacancy", "inconsistency_detect"),
        user_prompt=vacancy_inconsistency_detect_prompt(
            source_text=source_text,
            summary=summary,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_inconsistency_detect_llm_v1",
    )
    findings = _normalize_inconsistency_findings(result.payload.get("findings") or [])
    return LLMResult(
        payload={
            "findings": findings,
            "issues": [item["finding"] for item in findings],
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def copywrite_response_with_llm(*, approved_intent: str) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "response_copywriter"),
        user_prompt=response_copywriter_prompt(approved_intent=approved_intent),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="response_copywriter_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=400) or approved_intent[:400]},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_deletion_confirmation_with_llm(
    *,
    entity_type: str,
    has_active_interview: bool,
    has_active_matches: bool,
) -> LLMResult:
    result = _client.parse(
        schema=DeletionConfirmationSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "deletion_confirmation"),
        user_prompt=deletion_confirmation_prompt(
            entity_type=entity_type,
            has_active_interview=has_active_interview,
            has_active_matches=has_active_matches,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="deletion_confirmation_llm_v1",
    )
    return LLMResult(
        payload={
            "message": _clean_text(result.payload.get("message"), limit=350) or "",
            "is_explicit_confirmation_required": bool(
                result.payload.get("is_explicit_confirmation_required", True)
            ),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_small_talk_reply_with_llm(*, latest_user_message: str, current_step_guidance: str | None) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "small_talk"),
        user_prompt=small_talk_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="small_talk_reply_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=240) or ""},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_recovery_message_with_llm(*, state: str | None, allowed_actions: list[str], latest_user_message: str) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "recovery"),
        user_prompt=recovery_prompt(
            state=state,
            allowed_actions=allowed_actions,
            latest_user_message=latest_user_message,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="recovery_message_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=400) or ""},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_role_selection_reply_with_llm(*, latest_user_message: str | None = None) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "role_selection"),
        user_prompt=role_selection_prompt(latest_user_message=latest_user_message),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="role_selection_reply_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=350) or ""},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_interview_invitation_copy_with_llm(*, role_title: str | None) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "interview_invitation_copy"),
        user_prompt=interview_invitation_copy_prompt(role_title=role_title),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_invitation_copy_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=350) or ""},
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


def safe_merge_vacancy_summary(session, base_summary: dict, edit_request_text: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return merge_vacancy_summary_with_llm(base_summary, edit_request_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_summary_edit_fallback_to_baseline", error=str(exc))
    merged = dict(base_summary or {})
    merged["status"] = "draft"
    merged["manager_edit_notes"] = edit_request_text
    if not merged.get("approval_summary_text"):
        merged["approval_summary_text"] = build_vacancy_approval_summary_text(
            role_title=merged.get("role_title"),
            seniority_normalized=merged.get("seniority_normalized"),
            primary_tech_stack=merged.get("primary_tech_stack") or [],
            project_description_excerpt=merged.get("project_description_excerpt"),
            source_text=merged.get("project_description_excerpt") or "",
        )
    return LLMResult(
        payload=merged,
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_summary_edit_apply_v1",
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


def safe_build_interview_question_plan(session, vacancy, candidate_summary: dict, cv_text: str | None = None) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            result = build_interview_question_plan_with_llm(vacancy, candidate_summary, cv_text)
            questions = result.payload.get("questions") or []
            if len(questions) >= 4:
                return result
            raise RuntimeError("LLM returned too few interview questions.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_plan_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload=_fallback_interview_question_plan(vacancy, candidate_summary),
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


def safe_parse_interview_answer(
    session,
    *,
    question_text: str,
    candidate_answer: str,
    candidate_summary: dict | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return parse_interview_answer_with_llm(
                question_text=question_text,
                candidate_answer=candidate_answer,
                candidate_summary=candidate_summary,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_answer_parse_fallback_to_baseline", error=str(exc))

    answer_text = _clean_text(candidate_answer, limit=500) or ""
    lowered = answer_text.lower()
    ownership_level = "weak"
    if any(token in lowered for token in ["i designed", "i implemented", "i built", "i owned", "i led"]):
        ownership_level = "strong"
    elif any(token in lowered for token in ["i worked on", "i helped", "i supported", "i was involved"]):
        ownership_level = "mixed"
    technologies = [
        skill
        for skill in _normalize_skill_list((candidate_summary or {}).get("skills") or [])
        if skill in lowered
    ]
    is_concrete = len(answer_text.split()) >= 20 and any(
        marker in lowered for marker in ["because", "when", "after", "before", "project", "system", "service", "api"]
    )
    return LLMResult(
        payload={
            "answer_summary": answer_text,
            "technologies": technologies[:12],
            "systems_or_projects": [],
            "ownership_level": ownership_level,
            "is_concrete": is_concrete,
            "possible_profile_conflict": False,
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_answer_parse_v1",
    )


def safe_decide_interview_followup(
    session,
    *,
    question_text: str,
    question_kind: str,
    candidate_answer: str,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    follow_up_already_used: bool,
    answer_parse: dict | None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return decide_interview_followup_with_llm(
                question_text=question_text,
                question_kind=question_kind,
                candidate_answer=candidate_answer,
                candidate_summary=candidate_summary,
                vacancy_context=vacancy_context,
                follow_up_already_used=follow_up_already_used,
                answer_parse=answer_parse,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_followup_fallback_to_baseline", error=str(exc))

    parsed = answer_parse or {}
    answer_quality = "weak"
    if parsed.get("ownership_level") == "strong" and parsed.get("is_concrete"):
        answer_quality = "strong"
    elif parsed.get("ownership_level") in {"strong", "mixed"} or parsed.get("is_concrete"):
        answer_quality = "mixed"

    if follow_up_already_used:
        return LLMResult(
            payload={
                "answer_quality": answer_quality,
                "ask_followup": False,
                "followup_reason": "none",
                "followup_question": None,
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_followup_v1",
        )

    followup_reason = "none"
    followup_question = None
    ask_followup = False
    lowered = (candidate_answer or "").lower()
    if parsed.get("possible_profile_conflict"):
        ask_followup = True
        followup_reason = "verify"
        followup_question = "What exactly was your personal role in that part?"
    elif answer_quality == "strong":
        ask_followup = True
        followup_reason = "deepen"
        followup_question = "What was the biggest challenge there, and how did you handle it?"
    elif answer_quality == "mixed" and len(lowered.split()) >= 8:
        ask_followup = True
        followup_reason = "clarify"
        followup_question = "Could you walk me through a more specific example?"

    return LLMResult(
        payload={
            "answer_quality": answer_quality,
            "ask_followup": ask_followup,
            "followup_reason": followup_reason,
            "followup_question": followup_question,
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_followup_v1",
    )


def safe_bot_controller_decision(
    session,
    *,
    role: str | None,
    state: str | None,
    state_goal: str | None,
    allowed_actions: list[str],
    blocked_actions: list[str] | None,
    missing_requirements: list[str] | None,
    current_step_guidance: str | None,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return bot_controller_decision_with_llm(
                role=role,
                state=state,
                state_goal=state_goal,
                allowed_actions=allowed_actions,
                blocked_actions=blocked_actions,
                missing_requirements=missing_requirements,
                current_step_guidance=current_step_guidance,
                latest_user_message=latest_user_message,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("bot_controller_fallback_to_baseline", error=str(exc))

    text = (latest_user_message or "").strip().lower()
    payload = {
        "intent": "unknown",
        "tone": "friendly",
        "response_mode": "recover",
        "keep_current_state": True,
        "proposed_action": None,
        "response_text": current_step_guidance or "Please continue with the current step.",
        "reason_code": "ambiguous_message",
    }
    if any(token in text for token in ["hi", "hello", "hey", "thanks", "thank you"]):
        payload.update(
            {
                "intent": "small_talk",
                "response_mode": "redirect",
                "response_text": f"Happy to help. {current_step_guidance or 'Please continue with the current step.'}",
                "reason_code": "small_talk_redirect",
            }
        )
    elif any(
        token in text
        for token in [
            "what next",
            "what should i do",
            "help",
            "how does this work",
            "what do i do",
            "don't have a cv",
            "do not have a cv",
            "no cv",
            "no resume",
            "don't have resume",
            "do not have resume",
        ]
    ):
        payload.update(
            {
                "intent": "support_request",
                "response_mode": "answer",
                "response_text": current_step_guidance or "Please follow the current step shown in the chat.",
                "reason_code": "help",
            }
        )
    elif any(token in text for token in ["delete", "remove", "erase"]):
        payload.update(
            {
                "intent": "destructive_intent",
                "response_mode": "redirect",
                "response_text": "Profile or vacancy deletion requires an explicit confirmation flow. Please wait for that step.",
                "reason_code": "deletion_confirmation_needed",
            }
        )
    elif allowed_actions:
        payload.update(
            {
                "intent": "clarification_request",
                "response_mode": "clarify",
                "response_text": current_step_guidance
                or f"Please continue with the current step. Expected actions: {', '.join(allowed_actions)}.",
                "reason_code": "current_step_guidance",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_bot_controller_v2",
    )


def safe_state_assistance_decision(
    session,
    *,
    context,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> LLMResult:
    state_prompt_slug = getattr(context, "assistance_prompt_slug", None)
    if state_prompt_slug and should_use_llm_runtime(session):
        try:
            return state_assistance_decision_with_llm(
                state_prompt_slug=state_prompt_slug,
                context=context,
                latest_user_message=latest_user_message,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "state_assistance_fallback_to_baseline",
                state=context.state,
                prompt_slug=state_prompt_slug,
                error=str(exc),
            )

    text = (latest_user_message or "").strip().lower()
    response_text = context.help_text or context.guidance_text or "Please continue with the current step."
    intent = "support_request"
    reason_code = "state_help_fallback"
    suggested_action = None

    if any(token in text for token in ["hi", "hello", "hey", "thanks", "thank you"]):
        intent = "small_talk"
        reason_code = "small_talk_redirect"
        response_text = f"Happy to help. {context.guidance_text or response_text}"
    elif context.allowed_actions:
        suggested_action = context.allowed_actions[0]

    return LLMResult(
        payload={
            "response_text": response_text,
            "intent": intent,
            "keep_current_state": True,
            "suggested_action": suggested_action,
            "reason_code": reason_code,
        },
        model_name="baseline-deterministic",
        prompt_version=f"baseline_state_assistance_{context.state.lower()}_v1",
    )


def safe_candidate_summary_review_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_summary_review_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_summary_review_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance or "Review the summary and either approve it or tell me what is incorrect.",
        "proposed_action": None,
        "edit_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "summary_review_help_fallback",
    }
    if command in {"approve summary", "approve", "approve profile"}:
        payload.update(
            {
                "intent": "approve",
                "response_text": "Thanks. I will approve the summary and move to the next step.",
                "proposed_action": "approve_summary",
                "needs_follow_up": False,
                "reason_code": "summary_review_approve",
            }
        )
    elif command in {"change summary", "edit summary", "change", "edit"}:
        payload.update(
            {
                "intent": "needs_clarification",
                "response_text": "Tell me exactly what is incorrect in the summary, and I will update it once.",
                "needs_follow_up": True,
                "reason_code": "summary_review_needs_edit_details",
            }
        )
    elif command.startswith("edit summary:") or command.startswith("edit:"):
        edit_text = normalized_text.split(":", 1)[1].strip()
        if edit_text:
            payload.update(
                {
                    "intent": "correction",
                    "response_text": "Thanks. I will update the summary based on your correction.",
                    "proposed_action": "request_summary_change",
                    "edit_text": edit_text,
                    "needs_follow_up": False,
                    "reason_code": "summary_review_edit_request",
                }
            )
    elif any(token in lowered for token in ["how long", "when", "why", "how", "what if", "what should", "?"]):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance or "Review the summary and either approve it or tell me what is incorrect.",
                "needs_follow_up": True,
                "reason_code": "summary_review_help_question",
            }
        )
    elif any(
        token in lowered
        for token in ["wrong", "incorrect", "not ", "actually", "should be", "i work", "i use", "change to"]
    ):
        payload.update(
            {
                "intent": "correction",
                "response_text": "Thanks. I will update the summary based on your correction.",
                "proposed_action": "request_summary_change",
                "edit_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "summary_review_edit_request",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_summary_review_decision_v1",
    )


def safe_vacancy_summary_review_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return vacancy_summary_review_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_summary_review_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance or "Review the vacancy summary and either approve it or tell me what is incorrect.",
        "proposed_action": None,
        "edit_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "vacancy_summary_review_help_fallback",
    }
    if command in {"approve summary", "approve", "approve vacancy summary"}:
        payload.update(
            {
                "intent": "approve",
                "response_text": "Understood. I will lock the summary and move to the required vacancy details.",
                "proposed_action": "approve_summary",
                "needs_follow_up": False,
                "reason_code": "vacancy_summary_review_approve",
            }
        )
    elif command in {"change summary", "edit summary", "change", "edit"}:
        payload.update(
            {
                "intent": "needs_clarification",
                "response_text": "Tell me exactly what is incorrect in the vacancy summary, and I will update it once.",
                "needs_follow_up": True,
                "reason_code": "vacancy_summary_review_needs_edit_details",
            }
        )
    elif command.startswith("edit summary:") or command.startswith("edit:"):
        edit_text = normalized_text.split(":", 1)[1].strip()
        if edit_text:
            payload.update(
                {
                    "intent": "correction",
                    "response_text": "Understood. I will update the vacancy summary based on your correction.",
                    "proposed_action": "request_summary_change",
                    "edit_text": edit_text,
                    "needs_follow_up": False,
                    "reason_code": "vacancy_summary_review_edit_request",
                }
            )
    elif any(token in lowered for token in ["how long", "when", "why", "how", "what happens", "what should", "?"]):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance or "Review the vacancy summary and either approve it or tell me what is incorrect.",
                "needs_follow_up": True,
                "reason_code": "vacancy_summary_review_help_question",
            }
        )
    elif any(
        token in lowered
        for token in ["wrong", "incorrect", "not ", "actually", "should be", "change to", "the role", "the stack"]
    ):
        payload.update(
            {
                "intent": "correction",
                "response_text": "Understood. I will update the vacancy summary based on your correction.",
                "proposed_action": "request_summary_change",
                "edit_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "vacancy_summary_review_edit_request",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_summary_review_decision_v1",
    )


def safe_conduct_interview_turn(
    session,
    *,
    mode: str,
    candidate_first_name: str | None,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    interview_plan: list[dict] | None,
    current_question: dict | None,
    candidate_answer: str | None,
    answer_quality: str | None,
    follow_up_used: bool,
    follow_up_reason: str | None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return conduct_interview_turn_with_llm(
                mode=mode,
                candidate_first_name=candidate_first_name,
                candidate_summary=candidate_summary,
                vacancy_context=vacancy_context,
                interview_plan=interview_plan,
                current_question=current_question,
                candidate_answer=candidate_answer,
                answer_quality=answer_quality,
                follow_up_used=follow_up_used,
                follow_up_reason=follow_up_reason,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_conductor_fallback_to_baseline", error=str(exc))

    question_text = (current_question or {}).get("question") or ""
    if mode == "opening":
        first_name = f" {candidate_first_name}" if candidate_first_name else ""
        utterance = (
            f"Thanks for joining{first_name}. I reviewed your profile and prepared a few questions about your experience for this role. "
            f"Let's start. {question_text}"
        ).strip()
    elif mode in {"ask_main_question", "move_to_next_question"}:
        utterance = question_text
    elif mode == "ask_follow_up":
        utterance = question_text
    elif mode == "closing":
        utterance = "Thanks for sharing. That gives a good overview of your experience for the role."
    else:
        utterance = question_text or "Please continue."

    return LLMResult(
        payload={
            "mode": mode,
            "utterance": utterance[:500],
            "current_question_id": (current_question or {}).get("id"),
            "current_question_type": _normalize_question_type((current_question or {}).get("type")),
            "answer_quality": _normalize_answer_quality(answer_quality),
            "follow_up_used": follow_up_used,
            "follow_up_reason": _normalize_followup_reason(follow_up_reason),
            "move_to_next_question": mode == "move_to_next_question",
            "interview_complete": mode == "closing",
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_session_conductor_v1",
    )


def safe_rerank_candidates(session, *, vacancy, shortlisted_candidates: list[dict]) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            result = rerank_candidates_with_llm(
                vacancy=vacancy,
                shortlisted_candidates=shortlisted_candidates,
            )
            if result.payload.get("ranked_candidates"):
                return result
            raise RuntimeError("LLM returned empty rerank result.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_rerank_fallback_to_baseline", error=str(exc))

    ranked = []
    ordered = sorted(
        shortlisted_candidates,
        key=lambda item: (
            float(item.get("deterministic_score") or 0.0),
            float(item.get("embedding_score") or 0.0),
        ),
        reverse=True,
    )
    for rank, item in enumerate(ordered, start=1):
        ranked.append(
            {
                "candidate_ref": item["candidate_ref"],
                "rank": rank,
                "fit_score": round(float(item.get("deterministic_score") or 0.0), 4),
                "rationale": "Strong deterministic fit based on stack overlap, experience, and seniority alignment.",
            }
        )
    return LLMResult(
        payload={"ranked_candidates": ranked},
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_rerank_v1",
    )


def safe_detect_vacancy_inconsistencies(session, *, source_text: str, summary: dict, fallback_issues: list[str] | None = None) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return detect_vacancy_inconsistencies_with_llm(
                source_text=source_text,
                summary=summary,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_inconsistency_fallback_to_baseline", error=str(exc))

    issues = []
    for value in fallback_issues or []:
        issue = _clean_text(value, limit=240)
        if issue and issue not in issues:
            issues.append(issue)
    findings = [
        {
            "severity": "medium",
            "category": "other",
            "finding": issue,
        }
        for issue in issues
    ]
    return LLMResult(
        payload={"findings": findings, "issues": issues},
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_inconsistency_detect_v1",
    )


def safe_copywrite_response(session, *, approved_intent: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return copywrite_response_with_llm(approved_intent=approved_intent)
        except Exception as exc:  # noqa: BLE001
            logger.warning("response_copywriter_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload={"message": approved_intent[:400]},
        model_name="baseline-deterministic",
        prompt_version="baseline_response_copywriter_v1",
    )


def safe_build_deletion_confirmation(
    session,
    *,
    entity_type: str,
    has_active_interview: bool,
    has_active_matches: bool,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return build_deletion_confirmation_with_llm(
                entity_type=entity_type,
                has_active_interview=has_active_interview,
                has_active_matches=has_active_matches,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("deletion_confirmation_fallback_to_baseline", error=str(exc))

    side_effects = []
    if has_active_matches:
        side_effects.append("remove you from active matching")
    if has_active_interview:
        side_effects.append("cancel the active interview")
    side_effects_text = ""
    if side_effects:
        side_effects_text = " It will also " + " and ".join(side_effects) + "."
    noun = "profile" if entity_type == "candidate_profile" else "vacancy"
    return LLMResult(
        payload={
            "message": f"Please confirm deletion of this {noun}. Reply 'CONFIRM DELETE' to continue or 'Cancel delete' to keep it.{side_effects_text}",
            "is_explicit_confirmation_required": True,
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_deletion_confirmation_v1",
    )


def safe_build_small_talk_reply(session, *, latest_user_message: str, current_step_guidance: str | None) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return build_small_talk_reply_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("small_talk_fallback_to_baseline", error=str(exc))
    guidance = f" {current_step_guidance}" if current_step_guidance else ""
    return LLMResult(
        payload={"message": f"Happy to help.{guidance}".strip()},
        model_name="baseline-deterministic",
        prompt_version="baseline_small_talk_v1",
    )


def safe_build_recovery_message(session, *, state: str | None, allowed_actions: list[str], latest_user_message: str) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return build_recovery_message_with_llm(
                state=state,
                allowed_actions=allowed_actions,
                latest_user_message=latest_user_message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("recovery_message_fallback_to_baseline", error=str(exc))
    if allowed_actions:
        message = f"Please continue with the current step. Expected actions: {', '.join(allowed_actions)}."
    else:
        message = "Please continue with the current step."
    return LLMResult(
        payload={"message": message},
        model_name="baseline-deterministic",
        prompt_version="baseline_recovery_message_v1",
    )


def safe_build_role_selection_reply(session, *, latest_user_message: str | None = None) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return build_role_selection_reply_with_llm(latest_user_message=latest_user_message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("role_selection_fallback_to_baseline", error=str(exc))
    return LLMResult(
        payload={"message": "Choose your role: Candidate or Hiring Manager."},
        model_name="baseline-deterministic",
        prompt_version="baseline_role_selection_v1",
    )


def safe_build_interview_invitation_copy(session, *, role_title: str | None) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return build_interview_invitation_copy_with_llm(role_title=role_title)
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_invitation_copy_fallback_to_baseline", error=str(exc))
    role_text = f" for {role_title}" if role_title else ""
    return LLMResult(
        payload={"message": f"We found a strong-fit opportunity{role_text}. The next step is a short AI interview. Reply 'Accept interview' or 'Skip opportunity'."},
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_invitation_copy_v1",
    )
