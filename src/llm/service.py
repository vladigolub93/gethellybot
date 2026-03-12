from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Optional, TypeVar

from pydantic import BaseModel

from src.candidate_profile.skills_inventory import normalize_skill_list
from src.candidate_profile.question_parser import COUNTRY_CODES, parse_candidate_questions
from src.candidate_profile.summary_builder import build_approval_summary_text, build_candidate_summary
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.evaluation.scoring import build_interview_summary, evaluate_candidate
from src.interview.question_plan import build_question_plan
from src.llm.assets import build_user_facing_grounded_system_prompt, load_system_prompt
from src.llm.prompts import (
    STATE_ASSISTANCE_SYSTEM_PROMPT,
    bot_controller_prompt,
    candidate_cv_decision_prompt,
    candidate_cv_processing_decision_prompt,
    contact_required_decision_prompt,
    role_selection_decision_prompt,
    candidate_rerank_prompt,
    candidate_cv_prompt,
    candidate_questions_decision_prompt,
    candidate_ready_decision_prompt,
    candidate_vacancy_review_decision_prompt,
    candidate_verification_decision_prompt,
    candidate_questions_prompt,
    delete_confirmation_decision_prompt,
    interview_invitation_decision_prompt,
    interview_in_progress_decision_prompt,
    manager_review_decision_prompt,
    pre_interview_review_decision_prompt,
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
    match_card_copy_prompt,
    response_copywriter_prompt,
    role_selection_prompt,
    small_talk_prompt,
    vacancy_clarification_decision_prompt,
    vacancy_intake_decision_prompt,
    vacancy_jd_processing_decision_prompt,
    vacancy_open_decision_prompt,
    vacancy_clarifications_prompt,
    vacancy_inconsistency_detect_prompt,
    vacancy_jd_prompt,
    vacancy_summary_review_decision_prompt,
    vacancy_summary_edit_prompt,
)
from src.llm.state_assistance import state_assistance_prompt
from src.llm.schemas import (
    BotControllerDecisionSchema,
    CandidateCvDecisionSchema,
    CandidateCvProcessingDecisionSchema,
    CandidateRerankSchema,
    CandidateQuestionsDecisionSchema,
    CandidateQuestionParseSchema,
    CandidateReadyDecisionSchema,
    CandidateVacancyReviewDecisionSchema,
    CandidateVerificationDecisionSchema,
    ContactRequiredDecisionSchema,
    RoleSelectionDecisionSchema,
    DeleteConfirmationDecisionSchema,
    CandidateSummaryReviewDecisionSchema,
    CandidateSummarySchema,
    DeletionConfirmationSchema,
    InterviewAnswerParseSchema,
    InterviewEvaluationSchema,
    InterviewFollowupDecisionSchema,
    InterviewInvitationDecisionSchema,
    InterviewInProgressDecisionSchema,
    ManagerReviewDecisionSchema,
    PreInterviewReviewDecisionSchema,
    InterviewQuestionPlanSchema,
    InterviewSessionConductorTurnSchema,
    ResponseCopywriterSchema,
    StateAssistanceDecisionSchema,
    VacancyClarificationDecisionSchema,
    VacancyInconsistencySchema,
    VacancyIntakeDecisionSchema,
    VacancyJdProcessingDecisionSchema,
    VacancyOpenDecisionSchema,
    VacancyClarificationSchema,
    VacancySummaryReviewDecisionSchema,
    VacancySummarySchema,
)
from src.shared.text import normalize_command_text
from src.vacancy.question_parser import parse_vacancy_clarifications
from src.shared.hiring_taxonomy import (
    extract_domains,
    extract_hiring_stages,
    normalize_english_level,
)
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


def _clean_text_list(values, *, limit: int, item_limit: int) -> list[str]:
    result: list[str] = []
    seen = set()
    for value in values or []:
        cleaned = _clean_text(value, limit=limit)
        if not cleaned:
            continue
        normalized_key = cleaned.lower()
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        result.append(cleaned)
        if len(result) >= item_limit:
            break
    return result


def _clean_summary_text(value: Optional[str], *, limit: int) -> Optional[str]:
    if value is None:
        return None

    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None

    def _last_sentence_end(text: str, upper_bound: int) -> int:
        punctuation_positions = [
            text.rfind(". ", 0, upper_bound + 1),
            text.rfind("! ", 0, upper_bound + 1),
            text.rfind("? ", 0, upper_bound + 1),
            text.rfind(".", 0, upper_bound + 1),
            text.rfind("!", 0, upper_bound + 1),
            text.rfind("?", 0, upper_bound + 1),
        ]
        valid_positions = [position for position in punctuation_positions if position >= 0]
        return max(valid_positions) if valid_positions else -1

    if len(normalized) <= limit:
        if normalized.endswith((".", "!", "?")):
            return normalized
        sentence_end = _last_sentence_end(normalized, len(normalized))
        if sentence_end >= int(len(normalized) * 0.6):
            trimmed = normalized[: sentence_end + 1].strip()
            if trimmed:
                return trimmed
        return normalized

    min_sentence_cutoff = int(limit * 0.6)
    sentence_end = _last_sentence_end(normalized, limit)
    if sentence_end >= min_sentence_cutoff:
        trimmed = normalized[: sentence_end + 1].strip()
        if trimmed:
            return trimmed

    word_boundary = normalized.rfind(" ", 0, limit + 1)
    if word_boundary >= max(min_sentence_cutoff, 1):
        trimmed = normalized[:word_boundary].rstrip(" ,;:-")
        if trimmed:
            return trimmed

    return normalized[:limit].rstrip(" ,;:-")


def _trim_sentenceish_text(value: str, *, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return ""
    if len(normalized) <= limit:
        return normalized

    min_sentence_cutoff = int(limit * 0.6)
    punctuation_positions = [
        normalized.rfind(". ", 0, limit + 1),
        normalized.rfind("! ", 0, limit + 1),
        normalized.rfind("? ", 0, limit + 1),
        normalized.rfind(".", 0, limit + 1),
        normalized.rfind("!", 0, limit + 1),
        normalized.rfind("?", 0, limit + 1),
    ]
    valid_positions = [position for position in punctuation_positions if position >= 0]
    sentence_end = max(valid_positions) if valid_positions else -1
    if sentence_end >= min_sentence_cutoff:
        trimmed = normalized[: sentence_end + 1].strip()
        if trimmed:
            return trimmed

    word_boundary = normalized.rfind(" ", 0, limit + 1)
    if word_boundary >= max(min_sentence_cutoff, 1):
        trimmed = normalized[:word_boundary].rstrip(" ,;:-")
        if trimmed:
            return trimmed

    return normalized[:limit].rstrip(" ,;:-")


def _clean_interview_summary_text(value: Optional[str], *, limit: int) -> Optional[str]:
    if value is None:
        return None

    raw_text = str(value).strip()
    if not raw_text:
        return None

    paragraphs = [
        _trim_sentenceish_text(paragraph, limit=limit)
        for paragraph in re.split(r"\n\s*\n+", raw_text)
        if paragraph and paragraph.strip()
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if not paragraphs:
        return None

    if len(paragraphs) == 1:
        sentences = re.split(r"(?<=[.!?])\s+", paragraphs[0])
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        if len(sentences) >= 4:
            split_index = max(2, len(sentences) // 2)
            paragraphs = [
                " ".join(sentences[:split_index]).strip(),
                " ".join(sentences[split_index:]).strip(),
            ]

    normalized_paragraphs: list[str] = []
    current_length = 0
    for paragraph in paragraphs[:2]:
        paragraph = _trim_sentenceish_text(paragraph, limit=max(120, limit - current_length))
        if not paragraph:
            continue
        projected = current_length + len(paragraph) + (2 if normalized_paragraphs else 0)
        if normalized_paragraphs and projected > limit:
            break
        normalized_paragraphs.append(paragraph)
        current_length = projected

    if not normalized_paragraphs:
        return None
    return "\n\n".join(normalized_paragraphs).strip()


def _looks_like_transcript_dump(summary: Optional[str], answer_texts: list[str]) -> bool:
    normalized_summary = re.sub(r"\s+", " ", summary or "").strip().lower()
    normalized_answers = re.sub(r"\s+", " ", " ".join(answer_texts or [])).strip().lower()
    if not normalized_summary or not normalized_answers:
        return False
    if normalized_summary in normalized_answers:
        return True
    similarity = SequenceMatcher(None, normalized_summary[:1500], normalized_answers[:1500]).ratio()
    return similarity >= 0.72


def _normalize_skill_list(values: list[str]) -> list[str]:
    return normalize_skill_list(values or [], limit=12)


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


def _normalize_domain_list(values: list[str]) -> list[str]:
    return extract_domains(" ".join(str(item or "") for item in (values or [])), extra_values=values or [])


def _normalize_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
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
        "vacancy_skill_universe": getattr(vacancy, "vacancy_skill_universe", None),
        "project_description": getattr(vacancy, "project_description", None),
        "budget_min": getattr(vacancy, "budget_min", None),
        "budget_max": getattr(vacancy, "budget_max", None),
        "work_format": getattr(vacancy, "work_format", None),
        "office_city": getattr(vacancy, "office_city", None),
        "countries_allowed_json": getattr(vacancy, "countries_allowed_json", None),
        "required_english_level": getattr(vacancy, "required_english_level", None),
        "has_take_home_task": getattr(vacancy, "has_take_home_task", None),
        "take_home_paid": getattr(vacancy, "take_home_paid", None),
        "has_live_coding": getattr(vacancy, "has_live_coding", None),
        "hiring_stages_json": getattr(vacancy, "hiring_stages_json", None),
        "vacancy_domains": getattr(vacancy, "vacancy_domains", None),
    }


def _baseline_rerank_signals(item: dict) -> tuple[list[str], list[str]]:
    score_breakdown = item.get("score_breakdown") or {}
    matched_signals: list[str] = []
    concerns: list[str] = []

    if float(score_breakdown.get("core_skill_overlap_ratio") or 0.0) >= 0.75:
        matched_signals.append("Strong direct overlap with the core vacancy stack")
    elif float(score_breakdown.get("full_skill_overlap_ratio") or 0.0) >= 0.75:
        matched_signals.append("Strong overlap across the broader vacancy skill set")

    if float(score_breakdown.get("role_fit") or 0.0) >= 0.6:
        matched_signals.append("Role title and profile direction align well")

    if float(score_breakdown.get("domain_fit") or 0.0) >= 0.6:
        matched_signals.append("Candidate domain preferences align with the vacancy domain")

    if float(score_breakdown.get("process_fit") or 0.0) >= 0.85:
        matched_signals.append("Hiring process looks compatible with candidate preferences")
    elif float(score_breakdown.get("process_fit") or 0.0) <= 0.4:
        concerns.append("Hiring process may be heavier than the candidate prefers")

    if float(score_breakdown.get("english_fit") or 0.0) == 0.0:
        concerns.append("English requirement looks tighter than the candidate profile")

    if float(score_breakdown.get("location_fit") or 0.0) == 0.0:
        concerns.append("Location or office expectation may be a weaker fit")

    if not matched_signals:
        matched_signals.append("Solid deterministic fit on stack, experience, and seniority")
    if not concerns and float(score_breakdown.get("core_skill_overlap_ratio") or 0.0) < 0.5:
        concerns.append("Direct core stack overlap is not especially strong")

    return matched_signals[:3], concerns[:2]


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
        "approval_summary_text": _clean_summary_text(
            result.payload.get("approval_summary_text"),
            limit=900,
        ),
    }
    if not summary["approval_summary_text"]:
        summary["approval_summary_text"] = _clean_summary_text(
            build_approval_summary_text(
                headline=summary["headline"] or "software professional",
                source_text=source_text,
                years_experience=summary["years_experience"],
                skills=summary["skills"],
            ),
            limit=900,
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
            "approval_summary_text": _clean_summary_text(
                result.payload.get("approval_summary_text")
                or merged.get("approval_summary_text"),
                limit=900,
            ),
            "candidate_edit_notes": _clean_text(edit_request_text, limit=500),
        }
    )
    if not merged.get("approval_summary_text"):
        merged["approval_summary_text"] = _clean_summary_text(
            build_approval_summary_text(
                headline=merged.get("headline") or "software professional",
                source_text=merged.get("experience_excerpt") or "",
                years_experience=merged.get("years_experience"),
                skills=merged.get("skills") or [],
            ),
            limit=900,
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


def candidate_cv_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateCvDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "cv_pending_decision"),
        user_prompt=candidate_cv_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_cv_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "send_cv_text"}:
        proposed_action = None
    cv_text = _clean_text(result.payload.get("cv_text"), limit=4000)
    if proposed_action == "send_cv_text" and not cv_text:
        cv_text = _clean_text(latest_user_message, limit=4000)
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "cv_text": cv_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_cv_processing_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateCvProcessingDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "cv_processing_decision"),
        user_prompt=candidate_cv_processing_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_cv_processing_decision_llm_v1",
    )
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": None,
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
        "english_level": normalize_english_level(result.payload.get("english_level")),
        "preferred_domains_json": _normalize_domain_list(
            result.payload.get("preferred_domains_json") or []
        ),
        "show_take_home_task_roles": _normalize_bool(result.payload.get("show_take_home_task_roles")),
        "show_live_coding_roles": _normalize_bool(result.payload.get("show_live_coding_roles")),
    }
    if payload["country_code"] not in set(COUNTRY_CODES.values()):
        payload["country_code"] = None
    if not payload["preferred_domains_json"] and re.search(
        r"\b(any|no preference|open to anything|open to any domain|any domain)\b",
        text.lower(),
    ):
        payload["preferred_domains_json"] = ["any"]
    if not payload["preferred_domains_json"]:
        inferred_domains = extract_domains(text)
        if inferred_domains:
            payload["preferred_domains_json"] = inferred_domains
    return LLMResult(
        payload={key: value for key, value in payload.items() if value is not None},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_questions_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateQuestionsDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "questions_decision"),
        user_prompt=candidate_questions_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_questions_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "send_salary_location_work_format"}:
        proposed_action = None
    intent = _clean_text(result.payload.get("intent"), limit=80) or "help"
    response_text = _clean_text(result.payload.get("response_text"), limit=400)
    answer_text = _clean_text(result.payload.get("answer_text"), limit=1000)
    if proposed_action == "send_salary_location_work_format" and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=1000)
    return LLMResult(
        payload={
            "intent": intent,
            "response_text": response_text,
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def contact_required_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=ContactRequiredDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("entry", "contact_required_decision"),
        user_prompt=contact_required_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="contact_required_decision_llm_v1",
    )
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": None,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def role_selection_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=RoleSelectionDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("entry", "role_selection_decision"),
        user_prompt=role_selection_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="role_selection_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "candidate", "hiring_manager"}:
        proposed_action = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_ready_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateReadyDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "ready_decision"),
        user_prompt=candidate_ready_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_ready_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "delete_profile", "find_matching_vacancies", "update_matching_preferences", "record_matching_feedback"}:
        proposed_action = None
    answer_text = _clean_text(result.payload.get("answer_text"), limit=1000)
    if proposed_action in {"update_matching_preferences", "record_matching_feedback"} and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=1000)
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_vacancy_review_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateVacancyReviewDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "ready_decision"),
        user_prompt=candidate_vacancy_review_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_vacancy_review_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "apply_to_vacancy", "skip_vacancy", "update_matching_preferences", "record_matching_feedback"}:
        proposed_action = None
    answer_text = _clean_text(result.payload.get("answer_text"), limit=1000)
    if proposed_action in {"update_matching_preferences", "record_matching_feedback"} and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=1000)
    vacancy_slot = result.payload.get("vacancy_slot")
    if not isinstance(vacancy_slot, int) or vacancy_slot < 1:
        vacancy_slot = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "vacancy_slot": vacancy_slot,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def candidate_verification_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=CandidateVerificationDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("candidate", "verification_decision"),
        user_prompt=candidate_verification_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="candidate_verification_decision_llm_v1",
    )
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": _clean_text(result.payload.get("proposed_action"), limit=80),
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def manager_review_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=ManagerReviewDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("manager", "review_decision"),
        user_prompt=manager_review_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="manager_review_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "approve_candidate", "reject_candidate"}:
        proposed_action = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def pre_interview_review_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=PreInterviewReviewDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("manager", "review_decision"),
        user_prompt=pre_interview_review_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="pre_interview_review_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "interview_candidate", "skip_candidate", "update_vacancy_preferences", "record_vacancy_feedback"}:
        proposed_action = None
    answer_text = _clean_text(result.payload.get("answer_text"), limit=5000)
    if proposed_action in {"update_vacancy_preferences", "record_vacancy_feedback"} and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=5000)
    candidate_slot = result.payload.get("candidate_slot")
    if not isinstance(candidate_slot, int) or candidate_slot < 1:
        candidate_slot = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "candidate_slot": candidate_slot,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
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
        "approval_summary_text": _clean_summary_text(
            result.payload.get("approval_summary_text"),
            limit=900,
        ),
    }
    if not summary["approval_summary_text"]:
        summary["approval_summary_text"] = _clean_summary_text(
            build_vacancy_approval_summary_text(
                role_title=summary["role_title"],
                seniority_normalized=summary["seniority_normalized"],
                primary_tech_stack=summary["primary_tech_stack"],
                project_description_excerpt=summary["project_description_excerpt"],
                source_text=source_text,
            ),
            limit=900,
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
            "approval_summary_text": _clean_summary_text(
                result.payload.get("approval_summary_text")
                or merged.get("approval_summary_text"),
                limit=900,
            ),
            "manager_edit_notes": _clean_text(edit_request_text, limit=500),
        }
    )
    if not merged.get("approval_summary_text"):
        merged["approval_summary_text"] = _clean_summary_text(
            build_vacancy_approval_summary_text(
                role_title=merged.get("role_title"),
                seniority_normalized=merged.get("seniority_normalized"),
                primary_tech_stack=merged.get("primary_tech_stack") or [],
                project_description_excerpt=merged.get("project_description_excerpt"),
                source_text=merged.get("project_description_excerpt") or "",
            ),
            limit=900,
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


def vacancy_intake_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=VacancyIntakeDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("vacancy", "intake_pending_decision"),
        user_prompt=vacancy_intake_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_intake_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "send_job_description_text"}:
        proposed_action = None
    job_description_text = _clean_text(result.payload.get("job_description_text"), limit=5000)
    if proposed_action == "send_job_description_text" and not job_description_text:
        job_description_text = _clean_text(latest_user_message, limit=5000)
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "job_description_text": job_description_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def vacancy_jd_processing_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=VacancyJdProcessingDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("vacancy", "jd_processing_decision"),
        user_prompt=vacancy_jd_processing_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_jd_processing_decision_llm_v1",
    )
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": None,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def vacancy_clarification_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=VacancyClarificationDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("vacancy", "clarification_decision"),
        user_prompt=vacancy_clarification_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_clarification_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "send_vacancy_clarifications"}:
        proposed_action = None
    answer_text = _clean_text(result.payload.get("answer_text"), limit=5000)
    if proposed_action == "send_vacancy_clarifications" and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=5000)
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def vacancy_open_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=VacancyOpenDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("vacancy", "open_decision"),
        user_prompt=vacancy_open_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="vacancy_open_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {
        None,
        "find_matching_candidates",
        "update_vacancy_preferences",
        "record_vacancy_feedback",
        "create_new_vacancy",
        "list_open_vacancies",
        "delete_vacancy",
    }:
        proposed_action = None
    answer_text = _clean_text(result.payload.get("answer_text"), limit=5000)
    if proposed_action in {"update_vacancy_preferences", "record_vacancy_feedback"} and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=5000)
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def delete_confirmation_decision_with_llm(
    *,
    latest_user_message: str,
    entity_label: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=DeleteConfirmationDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("deletion", "confirmation_decision"),
        user_prompt=delete_confirmation_decision_prompt(
            latest_user_message=latest_user_message,
            entity_label=entity_label,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="delete_confirmation_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "confirm_delete", "cancel_delete"}:
        proposed_action = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def interview_invitation_decision_with_llm(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=InterviewInvitationDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("interview", "invitation_decision"),
        user_prompt=interview_invitation_decision_prompt(
            latest_user_message=latest_user_message,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_invitation_decision_llm_v1",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "accept_interview", "skip_opportunity"}:
        proposed_action = None
    return LLMResult(
        payload={
            "intent": _clean_text(result.payload.get("intent"), limit=80) or "help",
            "response_text": _clean_text(result.payload.get("response_text"), limit=400),
            "proposed_action": proposed_action,
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
        "office_city": _clean_text(result.payload.get("office_city"), limit=80),
        "required_english_level": normalize_english_level(result.payload.get("required_english_level")),
        "team_size": result.payload.get("team_size"),
        "project_description": _clean_text(result.payload.get("project_description"), limit=1200),
        "primary_tech_stack_json": _normalize_skill_list(
            result.payload.get("primary_tech_stack_json") or []
        ),
        "hiring_stages_json": extract_hiring_stages(
            " ".join(str(item) for item in (result.payload.get("hiring_stages_json") or [])),
            extra_values=result.payload.get("hiring_stages_json") or [],
        ),
        "has_take_home_task": _normalize_bool(result.payload.get("has_take_home_task")),
        "take_home_paid": _normalize_bool(result.payload.get("take_home_paid")),
        "has_live_coding": _normalize_bool(result.payload.get("has_live_coding")),
    }
    if not payload["hiring_stages_json"]:
        payload["hiring_stages_json"] = extract_hiring_stages(text)
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
        prompt_version="interview_evaluation_llm_v3",
    )
    score = result.payload.get("final_score")
    if score is None:
        score = 0.0
    score = max(0.0, min(1.0, float(score)))
    recommendation = (
        "advance" if str(result.payload.get("recommendation", "")).lower() == "advance" else "reject"
    )
    interview_summary = _clean_interview_summary_text(
        result.payload.get("interview_summary"),
        limit=1500,
    )
    if not interview_summary or _looks_like_transcript_dump(interview_summary, answer_texts):
        interview_summary = build_interview_summary(
            candidate_summary=candidate_summary,
            vacancy=vacancy,
            answer_texts=answer_texts,
            score=round(score, 4),
            recommendation=recommendation,
        )
    payload = {
        "final_score": round(score, 4),
        "strengths": result.payload.get("strengths") or [],
        "risks": result.payload.get("risks") or [],
        "recommendation": recommendation,
        "interview_summary": interview_summary or "",
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


def interview_in_progress_decision_with_llm(
    *,
    latest_user_message: str,
    current_question_text: str | None = None,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    normalized_text = (latest_user_message or "").strip()
    result = _client.parse(
        schema=InterviewInProgressDecisionSchema,
        system_prompt=build_user_facing_grounded_system_prompt("interview", "in_progress_decision"),
        user_prompt=interview_in_progress_decision_prompt(
            latest_user_message=latest_user_message,
            current_question_text=current_question_text,
            current_step_guidance=current_step_guidance,
            recent_context=recent_context,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="interview_in_progress_decision_llm_v2",
    )
    proposed_action = result.payload.get("proposed_action")
    if proposed_action not in {None, "answer_current_question", "accept_interview", "skip_opportunity", "cancel_interview"}:
        proposed_action = None
    intent = _clean_text(result.payload.get("intent"), limit=80) or "help"
    response_text = _clean_text(result.payload.get("response_text"), limit=400)
    answer_text = _clean_text(result.payload.get("answer_text"), limit=4000)
    if current_question_text:
        if _is_interview_start_confirmation(normalized_text):
            proposed_action = None
            intent = "help"
            answer_text = None
            response_text = _current_question_help_text(
                current_question_text,
                preface="Great. Here is the first interview question:",
            )
        elif _should_repeat_current_question(normalized_text):
            proposed_action = None
            intent = "help"
            answer_text = None
            response_text = _current_question_help_text(current_question_text)
    if proposed_action == "answer_current_question" and not answer_text:
        answer_text = _clean_text(latest_user_message, limit=4000)
    return LLMResult(
        payload={
            "intent": intent,
            "response_text": response_text,
            "proposed_action": proposed_action,
            "answer_text": answer_text,
            "keep_current_state": bool(result.payload.get("keep_current_state", True)),
            "needs_follow_up": bool(result.payload.get("needs_follow_up", False)),
            "reason_code": _clean_text(result.payload.get("reason_code"), limit=120),
        },
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
        prompt_version="interview_session_conductor_llm_v2",
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


def rerank_candidates_with_llm(
    *,
    vacancy,
    vacancy_context: dict | None = None,
    shortlisted_candidates: list[dict],
) -> LLMResult:
    result = _client.parse(
        schema=CandidateRerankSchema,
        system_prompt=load_system_prompt("matching", "candidate_rerank"),
        user_prompt=candidate_rerank_prompt(
            vacancy_context=vacancy_context or _vacancy_context(vacancy),
            shortlisted_candidates=shortlisted_candidates,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="matching_candidate_rerank_llm_v2",
    )
    ranked_candidates = []
    for item in result.payload.get("ranked_candidates") or []:
        if not isinstance(item, dict):
            continue
        candidate_ref = _clean_text(item.get("candidate_ref"), limit=120)
        rationale = _clean_text(item.get("rationale"), limit=280)
        matched_signals = _clean_text_list(item.get("matched_signals"), limit=140, item_limit=3)
        concerns = _clean_text_list(item.get("concerns"), limit=140, item_limit=2)
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
                "matched_signals": matched_signals,
                "concerns": concerns,
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


def build_match_card_copy_with_llm(
    *,
    audience: str,
    role_title: str | None,
    candidate_name: str | None = None,
    candidate_summary: str | None = None,
    project_summary: str | None = None,
    fit_reason: str | None = None,
    compensation_details: str | None = None,
    process_details: str | None = None,
    fit_band_label: str | None = None,
    gap_context: str | None = None,
    action_hint: str | None = None,
) -> LLMResult:
    result = _client.parse(
        schema=ResponseCopywriterSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "match_card_copy"),
        user_prompt=match_card_copy_prompt(
            audience=audience,
            role_title=role_title,
            candidate_name=candidate_name,
            candidate_summary=candidate_summary,
            project_summary=project_summary,
            fit_reason=fit_reason,
            compensation_details=compensation_details,
            process_details=process_details,
            fit_band_label=fit_band_label,
            gap_context=gap_context,
            action_hint=action_hint,
        ),
        primary_model=get_settings().openai_model_reasoning,
        prompt_version="match_card_copy_llm_v1",
    )
    return LLMResult(
        payload={"message": _clean_text(result.payload.get("message"), limit=700) or ""},
        model_name=result.model_name,
        prompt_version=result.prompt_version,
    )


def build_deletion_confirmation_with_llm(
    *,
    entity_type: str,
    entity_label: str | None,
    has_active_interview: bool,
    has_active_matches: bool,
) -> LLMResult:
    result = _client.parse(
        schema=DeletionConfirmationSchema,
        system_prompt=build_user_facing_grounded_system_prompt("messaging", "deletion_confirmation"),
        user_prompt=deletion_confirmation_prompt(
            entity_type=entity_type,
            entity_label=entity_label,
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


def _current_question_help_text(current_question_text: str | None, *, preface: str | None = None) -> str:
    question = (current_question_text or "").strip()
    if not question:
        return "Answer the current interview question in your own words. If something is unclear, ask me to clarify one specific part."
    lead = (preface or "Here is the current interview question:").strip()
    return f"{lead}\n{question}\n\nYou can answer in text, voice, or video."


def _is_interview_start_confirmation(text: str) -> bool:
    command = normalize_command_text(text)
    cleaned = " ".join(re.sub(r"[^\w\s]+", " ", command).split())
    candidates = {command, cleaned}
    return any(
        candidate in {
        "yes",
        "yes sure",
        "yes sounds good",
        "sounds good",
        "sure",
        "ok",
        "okay",
        "lets go",
        "let's go",
        "go ahead",
        "да",
        "да отлично",
        "давай",
        "ок",
        "хорошо",
        "супер",
        }
        for candidate in candidates
    )


def _should_repeat_current_question(text: str) -> bool:
    normalized = normalize_command_text(text)
    cleaned = " ".join(re.sub(r"[^\w\s]+", " ", normalized).split())
    lowered = (text or "").lower().strip()
    repeat_commands = {
        "repeat",
        "repeat question",
        "repeat the question",
        "what is the question",
        "where is the question",
        "what was the question",
        "can you repeat",
        "can you repeat the question",
        "can you clarify",
        "what do you mean",
        "what exactly are you asking",
        "what exactly you are asking",
        "а где вопрос",
        "какой вопрос",
        "повтори вопрос",
        "повтори пожалуйста вопрос",
        "в чем вопрос",
        "что за вопрос",
        "уточни вопрос",
    }
    if normalized in repeat_commands or cleaned in repeat_commands:
        return True
    return any(
        phrase in lowered
        for phrase in [
            "where is the question",
            "what is the question",
            "repeat the question",
            "what exactly are you asking",
            "what exactly you are asking",
            "а где вопрос",
            "повтори вопрос",
            "какой вопрос",
            "в чем вопрос",
        ]
    )


def safe_candidate_questions_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_questions_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_questions_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Answer the current question. I collect salary expectations, location, and work format one by one, and if anything is unclear you can ask me.",
        "proposed_action": None,
        "answer_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "candidate_questions_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "what happens after",
            "what next",
            "example",
            "gross or net",
            "net or gross",
            "which currency",
            "what currency",
            "what period",
            "per month or year",
            "how should i answer",
        ]
    ) or (normalized_text.endswith("?") and len(normalized_text) <= 200):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_candidate_questions_decision_v1",
        )

    if normalized_text:
        return LLMResult(
            payload={
                **payload,
                "intent": "answer",
                "response_text": None,
                "proposed_action": "send_salary_location_work_format",
                "answer_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "candidate_questions_answer_fallback",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_candidate_questions_decision_v1",
        )

    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_questions_decision_v1",
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


def safe_interview_in_progress_decision(
    session,
    *,
    latest_user_message: str,
    current_question_text: str | None = None,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return interview_in_progress_decision_with_llm(
                latest_user_message=latest_user_message,
                current_question_text=current_question_text,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_in_progress_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Answer the current interview question in your own words. If something is unclear, ask me to clarify one specific part.",
        "proposed_action": None,
        "answer_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "interview_in_progress_help_fallback",
    }
    if current_question_text and _is_interview_start_confirmation(normalized_text):
        return LLMResult(
            payload={
                **payload,
                "response_text": _current_question_help_text(
                    current_question_text,
                    preface="Great. Here is the first interview question:",
                ),
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_repeat_current_question",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )
    if current_question_text and _should_repeat_current_question(normalized_text):
        return LLMResult(
            payload={
                **payload,
                "response_text": _current_question_help_text(current_question_text),
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_repeat_current_question",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )
    if command in {"accept interview", "accept"}:
        return LLMResult(
            payload={
                **payload,
                "intent": "accept",
                "response_text": "Understood. I will handle that interview invitation.",
                "proposed_action": "accept_interview",
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_accept_other_invitation",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )
    if command in {"skip opportunity", "skip"}:
        return LLMResult(
            payload={
                **payload,
                "intent": "skip",
                "response_text": "Understood. I will skip that opportunity.",
                "proposed_action": "skip_opportunity",
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_skip_other_invitation",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )
    if command in {"cancel interview", "stop interview", "end interview", "abort interview", "quit interview"}:
        return LLMResult(
            payload={
                **payload,
                "intent": "cancel_interview",
                "response_text": "Understood. I will cancel this interview.",
                "proposed_action": "cancel_interview",
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_cancel_interview",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )
    if any(
        token in lowered
        for token in [
            "what do you mean",
            "can you repeat",
            "can you clarify",
            "i do not understand",
            "what exactly are you asking",
            "how should i answer",
            "can i answer by voice",
            "can i send video",
            "how long",
        ]
    ) or (normalized_text.endswith("?") and len(normalized_text) <= 200):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )

    if normalized_text:
        return LLMResult(
            payload={
                **payload,
                "intent": "answer",
                "response_text": None,
                "proposed_action": "answer_current_question",
                "answer_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "interview_in_progress_answer_fallback",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_interview_in_progress_decision_v1",
        )

    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_in_progress_decision_v1",
    )


def safe_interview_invitation_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return interview_invitation_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview_invitation_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "This is a short interview for a matching role. You can accept it now or skip this opportunity.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "interview_invitation_help_fallback",
    }
    if command in {"accept interview", "accept"}:
        payload.update(
            {
                "intent": "accept",
                "response_text": "Thanks. I will start the interview.",
                "proposed_action": "accept_interview",
                "needs_follow_up": False,
                "reason_code": "interview_invitation_accept",
            }
        )
    elif command in {"skip opportunity", "skip"}:
        payload.update(
            {
                "intent": "skip",
                "response_text": "Understood. I will skip this opportunity.",
                "proposed_action": "skip_opportunity",
                "needs_follow_up": False,
                "reason_code": "interview_invitation_skip",
            }
        )
    elif any(
        token in lowered
        for token in [
            "what is this",
            "how long",
            "voice",
            "video",
            "text",
            "what happens if i skip",
            "what happens after",
            "why was i invited",
            "why",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "This is a short interview for a matching role. You can accept it now or skip this opportunity.",
                "needs_follow_up": True,
                "reason_code": "interview_invitation_help_question",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_invitation_decision_v1",
    )


def safe_candidate_cv_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_cv_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_cv_decision_fallback", error=str(exc))

    normalized_text = " ".join((latest_user_message or "").strip().split())
    lowered = normalized_text.lower()

    meta_phrases = (
        "here is my cv",
        "here's my cv",
        "here is my resume",
        "here's my resume",
        "sending my cv",
        "sending my resume",
        "i will send my cv",
        "i'll send my cv",
        "i will send it now",
        "i'll send it now",
        "send it now",
        "one sec",
        "one second",
        "wait a sec",
        "hold on",
        "see attached",
        "attached here",
        "cv attached",
        "resume attached",
    )

    def _looks_like_meta_message(value: str) -> bool:
        if not value:
            return False
        if value in meta_phrases:
            return True
        return any(
            value.startswith(f"{phrase}.") or value.startswith(f"{phrase},")
            for phrase in meta_phrases
        )

    def _looks_like_experience_input(value: str) -> bool:
        if not value or "?" in value:
            return False
        if _looks_like_meta_message(value):
            return False

        word_count = len(value.split())
        if len(value) >= 80:
            return True
        if ("\n" in latest_user_message or "," in value or ";" in value) and len(value) >= 24:
            return True
        if re.search(r"\b\d+\+?\b", value) and re.search(
            r"\b(year|years|yr|yrs|month|months|experience|engineer|developer|frontend|backend|full[- ]stack|"
            r"python|java|javascript|typescript|react|node|go|aws|django|postgres|sql|docker|kubernetes)\b",
            value,
        ):
            return True
        return word_count >= 8

    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "You can upload a CV, paste a work summary, send a LinkedIn PDF, or describe your experience in a voice message.",
        "proposed_action": None,
        "cv_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "candidate_cv_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "skip",
            "later",
            "linkedin",
            "pdf",
            "no cv",
            "no resume",
            "do not have",
            "don't have",
            "dont have",
            "what should i send",
            "what do i send",
            "what can i send",
            "what next",
            "?",
        ]
    ) or _looks_like_meta_message(lowered):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_candidate_cv_decision_v1",
        )

    if _looks_like_experience_input(lowered):
        return LLMResult(
            payload={
                **payload,
                "intent": "experience_input",
                "response_text": None,
                "proposed_action": "send_cv_text",
                "cv_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "candidate_cv_text_submission",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_candidate_cv_decision_v1",
        )

    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_cv_decision_v1",
    )


def safe_candidate_cv_processing_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_cv_processing_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_cv_processing_decision_fallback", error=str(exc))

    return LLMResult(
        payload={
            "intent": "processing_wait",
            "response_text": current_step_guidance
            or "Still on it. I’m parsing your CV and I’ll send the summary here as soon as it’s ready.",
            "proposed_action": None,
            "keep_current_state": True,
            "needs_follow_up": True,
            "reason_code": "candidate_cv_processing_wait_fallback",
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_cv_processing_decision_v1",
    )


def safe_vacancy_intake_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return vacancy_intake_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_intake_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "You can paste the job details here, upload a JD, or send the role context by voice.",
        "proposed_action": None,
        "job_description_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "vacancy_intake_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "no formal jd",
            "no jd",
            "just paste",
            "paste the job",
            "what should i send",
            "what do i include",
            "what to include",
            "what next",
            "voice",
            "text",
            "?",
        ]
    ):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_vacancy_intake_decision_v1",
        )

    if normalized_text:
        return LLMResult(
            payload={
                **payload,
                "intent": "jd_input",
                "response_text": None,
                "proposed_action": "send_job_description_text",
                "job_description_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "vacancy_intake_text_submission",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_vacancy_intake_decision_v1",
        )

    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_intake_decision_v1",
    )


def safe_vacancy_jd_processing_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return vacancy_jd_processing_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_jd_processing_decision_fallback", error=str(exc))

    return LLMResult(
        payload={
            "intent": "processing_wait",
            "response_text": current_step_guidance
            or "Still working on it. I’m turning the job description into a short vacancy summary now.",
            "proposed_action": None,
            "keep_current_state": True,
            "needs_follow_up": True,
            "reason_code": "vacancy_jd_processing_wait_fallback",
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_jd_processing_decision_v1",
    )


def safe_vacancy_clarification_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return vacancy_clarification_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_clarification_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Answer the current vacancy question. I collect budget, work format, countries, team size, project context, and stack one by one.",
        "proposed_action": None,
        "answer_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "vacancy_clarification_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "what exactly",
            "what else",
            "what do you need",
            "what should i include",
            "gross or net",
            "net or gross",
            "which currency",
            "what currency",
            "what period",
            "what countries",
            "what happens next",
            "?",
        ]
    ):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_vacancy_clarification_decision_v1",
        )

    if normalized_text:
        return LLMResult(
            payload={
                **payload,
                "intent": "clarification_answer",
                "response_text": None,
                "proposed_action": "send_vacancy_clarifications",
                "answer_text": normalized_text,
                "needs_follow_up": False,
                "reason_code": "vacancy_clarification_answer_submission",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_vacancy_clarification_decision_v1",
        )

    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_clarification_decision_v1",
    )


def safe_candidate_ready_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_ready_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_ready_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Your profile is ready for matching. I will message you when there is a strong opportunity and you do not need to do anything else right now.",
        "proposed_action": None,
        "answer_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "candidate_ready_help_fallback",
    }
    if command in {"delete profile", "delete my profile", "remove profile"}:
        payload.update(
            {
                "intent": "delete_request",
                "response_text": "Understood. I can help you delete your profile.",
                "proposed_action": "delete_profile",
                "needs_follow_up": False,
                "reason_code": "candidate_ready_delete_profile",
            }
        )
    elif any(
        token in lowered
        for token in [
            "find me a vacancy",
            "find a vacancy for me",
            "find me a job",
            "find vacancies",
            "find jobs",
            "check vacancies",
            "check open roles",
            "check matching again",
            "run matching",
            "any vacancy for me",
            "any vacancies for me",
            "is there a vacancy for me",
            "найди вакансию",
            "найди мне вакансию",
            "поищи вакансию",
            "есть ли вакансия",
            "есть ли вакансии",
            "есть что-то для меня",
            "запусти мэтчинг",
            "обнови мэтчинг",
        ]
    ):
        payload.update(
            {
                "intent": "find_matching_vacancies",
                "response_text": "Got it. I can check current open roles for your profile now.",
                "proposed_action": "find_matching_vacancies",
                "needs_follow_up": False,
                "reason_code": "candidate_ready_find_matching_vacancies",
            }
        )
    elif any(
        token in lowered
        for token in [
            "what happens now",
            "what do i do next",
            "what should i do next",
            "when will i hear",
            "when will i get",
            "when will i hear back",
            "when will i get opportunities",
            "when will i get a match",
            "how does matching work",
            "do i need to do anything",
            "do i need anything else",
            "?",
        ]
        ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Your profile is ready for matching. I will message you when there is a strong opportunity and you do not need to do anything else right now.",
                "needs_follow_up": True,
                "reason_code": "candidate_ready_help_question",
            }
        )
    else:
        parsed = dict(safe_parse_candidate_questions(session, normalized_text).payload or {})
        update_markers = [
            "change",
            "update",
            "switch",
            "set",
            "now",
            "only",
            "instead",
            "prefer",
            "from ",
            "теперь",
            "измени",
            "обнови",
            "поменяй",
            "поставь",
            "предпочитаю",
            "только",
            "лишь",
            "больше не",
            "не показывай",
            "показывай",
        ]
        feedback_markers = [
            "keep missing",
            "do not fit",
            "don't fit",
            "not right for me",
            "do not like these roles",
            "don't like these roles",
            "do not like these vacancies",
            "don't like these vacancies",
            "keep skipping",
            "wrong for me",
            "too low",
            "не подходят",
            "не нравится",
            "не нравятся",
            "не то",
            "скипаю",
            "пропускаю",
            "мимо",
        ]
        has_explicit_update_markers = any(
            marker in lowered
            for marker in [
                "change",
                "update",
                "switch",
                "set",
                "now",
                "instead",
                "теперь",
                "измени",
                "обнови",
                "поменяй",
                "убери",
                "добавь",
            ]
        )
        has_feedback_markers = any(marker in lowered for marker in feedback_markers)
        if parsed and (has_explicit_update_markers or (len(normalized_text.split()) <= 18 and not has_feedback_markers)):
            payload.update(
                {
                    "intent": "update_preferences",
                    "response_text": "Got it. I can update your matching preferences.",
                    "proposed_action": "update_matching_preferences",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "candidate_ready_update_preferences",
                }
            )
        elif has_feedback_markers:
            payload.update(
                {
                    "intent": "matching_feedback",
                    "response_text": "Got it. Tell me what keeps missing and I can save that feedback or turn it into a preference update.",
                    "proposed_action": "record_matching_feedback",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "candidate_ready_matching_feedback",
                }
            )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_ready_decision_v1",
    )


def safe_candidate_vacancy_review_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_vacancy_review_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_vacancy_review_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Review the current vacancy cards and use the Apply or Skip buttons under each role.",
        "proposed_action": None,
        "answer_text": None,
        "vacancy_slot": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "candidate_vacancy_review_help_fallback",
    }

    match = re.search(r"\b(apply|connect|skip)(?:\s+vacancy)?\s+(\d+)\b", command)
    if match is not None:
        verb = match.group(1)
        slot = int(match.group(2))
        if verb in {"apply", "connect"}:
            payload.update(
                {
                    "intent": "apply_to_vacancy",
                    "response_text": f"Understood. I will move forward with vacancy {slot}.",
                    "proposed_action": "apply_to_vacancy",
                    "vacancy_slot": slot,
                    "needs_follow_up": False,
                    "reason_code": "candidate_vacancy_review_apply_to_vacancy",
                }
            )
        else:
            payload.update(
                {
                    "intent": "skip_vacancy",
                    "response_text": f"Understood. I will skip vacancy {slot}.",
                    "proposed_action": "skip_vacancy",
                    "vacancy_slot": slot,
                    "needs_follow_up": False,
                    "reason_code": "candidate_vacancy_review_skip_vacancy",
                }
            )
    elif any(
        token in lowered
        for token in [
            "what does this mean",
            "how does this work",
            "what happens after",
            "what if i apply",
            "what if i skip",
            "explain",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Review the current vacancy cards and use the Apply or Skip buttons under each role.",
                "needs_follow_up": True,
                "reason_code": "candidate_vacancy_review_help_question",
            }
        )
    else:
        parsed = dict(safe_parse_candidate_questions(session, normalized_text).payload or {})
        update_markers = [
            "change",
            "update",
            "switch",
            "set",
            "now",
            "only",
            "instead",
            "prefer",
            "from ",
            "теперь",
            "измени",
            "обнови",
            "поменяй",
            "поставь",
            "предпочитаю",
            "только",
            "больше не",
            "не показывай",
            "показывай",
        ]
        feedback_markers = [
            "keep missing",
            "do not fit",
            "don't fit",
            "not right for me",
            "keep skipping",
            "wrong for me",
            "too low",
            "не подходят",
            "не нравится",
            "не нравятся",
            "не то",
            "скипаю",
            "пропускаю",
            "мимо",
        ]
        has_explicit_update_markers = any(
            marker in lowered
            for marker in [
                "change",
                "update",
                "switch",
                "set",
                "now",
                "instead",
                "теперь",
                "измени",
                "обнови",
                "поменяй",
                "убери",
                "добавь",
            ]
        )
        has_feedback_markers = any(marker in lowered for marker in feedback_markers)
        if parsed and (has_explicit_update_markers or (len(normalized_text.split()) <= 18 and not has_feedback_markers)):
            payload.update(
                {
                    "intent": "update_preferences",
                    "response_text": "Got it. I can update your matching preferences from here.",
                    "proposed_action": "update_matching_preferences",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "candidate_vacancy_review_update_preferences",
                }
            )
        elif has_feedback_markers:
            payload.update(
                {
                    "intent": "matching_feedback",
                    "response_text": "Got it. Tell me what keeps missing and I can save that feedback or turn it into a preference update right here.",
                    "proposed_action": "record_matching_feedback",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "candidate_vacancy_review_matching_feedback",
                }
            )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_vacancy_review_decision_v1",
    )


def safe_candidate_verification_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return candidate_verification_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("candidate_verification_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Record a short verification video with the phrase I gave you, and send it here when you are ready.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "candidate_verification_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "what did you hear",
            "what did you transcribe",
            "what transcript",
            "what did it hear",
            "show transcript",
            "show me the transcript",
            "как ты транскриб",
            "что ты услыш",
            "что ты распознал",
            "что ты расшифровал",
            "какая расшифровка",
        ]
    ):
        payload.update(
            {
                "intent": "transcript_debug",
                "response_text": "I can show what I heard from the last verification video.",
                "proposed_action": "show_last_verification_transcript",
                "needs_follow_up": False,
                "reason_code": "candidate_verification_show_transcript",
            }
        )
    elif any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "cannot",
            "can't",
            "cant",
            "later",
            "desktop",
            "camera",
            "video",
            "phrase",
            "what happens after",
            "what next",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Record a short verification video with the phrase I gave you, and send it here when you are ready.",
                "needs_follow_up": True,
                "reason_code": "candidate_verification_help_question",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_verification_decision_v1",
    )


def safe_manager_review_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return manager_review_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("manager_review_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Review the candidate package, then approve or reject when you are ready.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "manager_review_help_fallback",
    }
    if command in {"approve candidate", "approve"}:
        payload.update(
            {
                "intent": "approve_candidate",
                "response_text": "Understood. I will approve the candidate and prepare the handoff.",
                "proposed_action": "approve_candidate",
                "needs_follow_up": False,
                "reason_code": "manager_review_approve_candidate",
            }
        )
    elif command in {"reject candidate", "reject"}:
        payload.update(
            {
                "intent": "reject_candidate",
                "response_text": "Understood. I will reject the candidate.",
                "proposed_action": "reject_candidate",
                "needs_follow_up": False,
                "reason_code": "manager_review_reject_candidate",
            }
        )
    elif any(
        token in lowered
        for token in [
            "what does this mean",
            "how should i read",
            "explain",
            "what are the risks",
            "what are the strengths",
            "why was this candidate selected",
            "what happens if i approve",
            "what happens if i reject",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Review the candidate package, then approve or reject when you are ready.",
                "needs_follow_up": True,
                "reason_code": "manager_review_help_question",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_manager_review_decision_v1",
    )


def safe_pre_interview_review_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return pre_interview_review_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("pre_interview_review_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Review the current candidate cards and use the Connect or Skip buttons under each profile.",
        "proposed_action": None,
        "answer_text": None,
        "candidate_slot": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "pre_interview_review_help_fallback",
    }

    match = re.search(r"\b(connect|approve|interview|skip)(?:\s+candidate)?\s+(\d+)\b", command)
    if match is not None:
        verb = match.group(1)
        slot = int(match.group(2))
        if verb in {"connect", "approve", "interview"}:
            payload.update(
                {
                    "intent": "interview_candidate",
                    "response_text": f"Understood. I will approve candidate {slot} for the next step.",
                    "proposed_action": "interview_candidate",
                    "candidate_slot": slot,
                    "needs_follow_up": False,
                    "reason_code": "pre_interview_review_connect_candidate",
                }
            )
        else:
            payload.update(
                {
                    "intent": "skip_candidate",
                    "response_text": f"Understood. I will skip candidate {slot}.",
                    "proposed_action": "skip_candidate",
                    "candidate_slot": slot,
                    "needs_follow_up": False,
                    "reason_code": "pre_interview_review_skip_candidate",
                }
            )
    elif any(
        token in lowered
        for token in [
            "what does this mean",
            "how should i read",
            "why was candidate",
            "what happens after connect",
            "how does this work",
            "explain",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Review the current candidate cards and use the Interview or Skip buttons under each profile.",
                "needs_follow_up": True,
                "reason_code": "pre_interview_review_help_question",
            }
        )
    else:
        parsed = dict(safe_parse_vacancy_clarifications(session, normalized_text).payload or {})
        update_markers = [
            "change",
            "update",
            "switch",
            "set",
            "now",
            "instead",
            "budget",
            "english",
            "stages",
            "stack",
            "format",
            "city",
            "теперь",
            "измени",
            "обнови",
            "поменяй",
            "бюджет",
            "английский",
            "англійська",
            "этапы",
            "етапи",
            "стек",
            "формат",
            "город",
            "місто",
            "убери",
            "добавь",
        ]
        feedback_markers = [
            "keep missing",
            "not right",
            "missing the mark",
            "too weak",
            "feel weak",
            "weak on",
            "too low",
            "keep skipping",
            "wrong candidates",
            "bad fit",
            "не подходят",
            "не те",
            "не то",
            "скипаю",
            "пропускаю",
            "слабые",
            "мимо",
        ]
        has_explicit_update_markers = any(
            marker in lowered
            for marker in [
                "change",
                "update",
                "switch",
                "set",
                "now",
                "instead",
                "теперь",
                "измени",
                "обнови",
                "поменяй",
                "убери",
                "добавь",
            ]
        )
        has_feedback_markers = any(marker in lowered for marker in feedback_markers)
        has_specific_update_values = any(char.isdigit() for char in normalized_text) or any(
            marker in lowered
            for marker in [
                "remote",
                "hybrid",
                "office",
                "b1",
                "b2",
                "c1",
                "c2",
                "a1",
                "a2",
                "native",
                "no live coding",
                "no take-home",
                "no take home",
                "paid take-home",
                "unpaid take-home",
            ]
        )
        if parsed and (
            has_explicit_update_markers or (has_specific_update_values and not has_feedback_markers)
        ):
            payload.update(
                {
                    "intent": "update_vacancy_preferences",
                    "response_text": "Got it. I can update this vacancy from here.",
                    "proposed_action": "update_vacancy_preferences",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "pre_interview_review_update_vacancy",
                }
            )
        elif has_feedback_markers:
            payload.update(
                {
                    "intent": "vacancy_feedback",
                    "response_text": "Got it. Tell me what keeps missing and I can save that feedback or turn it into a vacancy update right here.",
                    "proposed_action": "record_vacancy_feedback",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "pre_interview_review_feedback",
                }
            )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_pre_interview_review_decision_v1",
    )


def safe_contact_required_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return contact_required_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("contact_required_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Please share your contact using the Telegram button so I can continue onboarding you here.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "contact_required_help_fallback",
    }
    if any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "contact",
            "phone",
            "number",
            "skip",
            "later",
            "privacy",
            "what happens next",
            "?",
        ]
    ):
        return LLMResult(
            payload=payload,
            model_name="baseline-deterministic",
            prompt_version="baseline_contact_required_decision_v1",
        )

    return LLMResult(
        payload={
            **payload,
            "intent": "redirect",
            "reason_code": "contact_required_redirect",
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_contact_required_decision_v1",
    )


def safe_role_selection_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return role_selection_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("role_selection_decision_fallback", error=str(exc))

    normalized_text = normalize_command_text(latest_user_message or "")
    lowered = (latest_user_message or "").strip().lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Choose Candidate if you are looking for a job, or Hiring Manager if you want to hire for a role.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "role_selection_help_fallback",
    }
    if normalized_text == "candidate":
        payload.update(
            {
                "intent": "role_selection",
                "response_text": "Understood. I will start the candidate flow.",
                "proposed_action": "candidate",
                "needs_follow_up": False,
                "reason_code": "role_selection_candidate",
            }
        )
    elif normalized_text == "hiring manager":
        payload.update(
            {
                "intent": "role_selection",
                "response_text": "Understood. I will start the hiring manager flow.",
                "proposed_action": "hiring_manager",
                "needs_follow_up": False,
                "reason_code": "role_selection_hiring_manager",
            }
        )
    elif any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "role",
            "difference",
            "which",
            "what happens next",
            "?",
        ]
    ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Choose Candidate if you are looking for a job, or Hiring Manager if you want to hire for a role.",
                "needs_follow_up": True,
                "reason_code": "role_selection_help_question",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_role_selection_decision_v1",
    )


def safe_vacancy_open_decision(
    session,
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            return vacancy_open_decision_with_llm(
                latest_user_message=latest_user_message,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vacancy_open_decision_fallback", error=str(exc))

    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    payload = {
        "intent": "help",
        "response_text": current_step_guidance
        or "Your vacancy is open for matching. You do not need to do anything else right now, and I will bring qualified candidates once they are ready.",
        "proposed_action": None,
        "answer_text": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "vacancy_open_help_fallback",
    }
    if command in {"delete vacancy", "delete job", "remove vacancy"}:
        payload.update(
            {
                "intent": "delete_request",
                "response_text": "Understood. I can help you remove this vacancy.",
                "proposed_action": "delete_vacancy",
                "needs_follow_up": False,
                "reason_code": "vacancy_open_delete_request",
            }
        )
    elif any(
        token in lowered
        for token in [
            "find candidates",
            "find me candidates",
            "look for candidates",
            "search candidates",
            "refresh matching",
            "run matching",
            "check candidates again",
            "any candidates",
            "are there candidates",
            "найди кандидатов",
            "поищи кандидатов",
            "есть ли кандидаты",
            "обнови мэтчинг",
            "запусти мэтчинг",
        ]
    ):
        payload.update(
            {
                "intent": "find_matching_candidates",
                "response_text": "Got it. I can refresh matching for this vacancy now.",
                "proposed_action": "find_matching_candidates",
                "needs_follow_up": False,
                "reason_code": "vacancy_open_find_matching_candidates",
            }
        )
    elif any(
        token in lowered
        for token in [
            "create another vacancy",
            "create a new vacancy",
            "create one more vacancy",
            "create second vacancy",
            "create another role",
            "open another vacancy",
            "open a new vacancy",
            "add another vacancy",
            "add one more vacancy",
            "second vacancy",
        ]
    ):
        payload.update(
            {
                "intent": "create_new_vacancy",
                "response_text": "Nice. We can open another vacancy right now.",
                "proposed_action": "create_new_vacancy",
                "needs_follow_up": False,
                "reason_code": "vacancy_open_create_request",
            }
        )
    elif any(
        token in lowered
        for token in [
            "show my vacancies",
            "show my open vacancies",
            "show open vacancies",
            "list my vacancies",
            "list my open vacancies",
            "list open vacancies",
            "what vacancies do i have",
            "what open vacancies do i have",
            "see my vacancies",
            "see my open vacancies",
            "see open vacancies",
        ]
    ):
        payload.update(
            {
                "intent": "list_open_vacancies",
                "response_text": "Sure. I can show your active vacancies.",
                "proposed_action": "list_open_vacancies",
                "needs_follow_up": False,
                "reason_code": "vacancy_open_list_request",
            }
        )
    elif any(
        token in lowered
        for token in [
            "what happens now",
            "what next",
            "when will i see",
            "when will i get",
            "when candidate",
            "when match",
            "how matching",
            "do i need to do anything",
            "why am i not seeing",
            "?",
        ]
        ):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance
                or "Your vacancy is open for matching. You do not need to do anything else right now, and I will bring qualified candidates once they are ready.",
                "needs_follow_up": True,
                "reason_code": "vacancy_open_help_question",
            }
        )
    else:
        parsed = dict(safe_parse_vacancy_clarifications(session, normalized_text).payload or {})
        update_markers = [
            "change",
            "update",
            "switch",
            "set",
            "now",
            "instead",
            "budget",
            "english",
            "stages",
            "stack",
            "format",
            "теперь",
            "измени",
            "обнови",
            "поменяй",
            "бюджет",
            "английский",
            "англійська",
            "этапы",
            "етапи",
            "стек",
            "формат",
            "убери",
            "добавь",
        ]
        feedback_markers = [
            "keep missing",
            "not right",
            "missing the mark",
            "too weak",
            "feel weak",
            "weak on",
            "too low",
            "keep skipping",
            "wrong candidates",
            "bad fit",
            "не подходят",
            "не те",
            "не то",
            "скипаю",
            "пропускаю",
            "слабые",
            "мимо",
        ]
        has_explicit_update_markers = any(
            marker in lowered
            for marker in [
                "change",
                "update",
                "switch",
                "set",
                "now",
                "instead",
                "теперь",
                "измени",
                "обнови",
                "поменяй",
                "убери",
                "добавь",
            ]
        )
        has_feedback_markers = any(marker in lowered for marker in feedback_markers)
        has_specific_update_values = any(char.isdigit() for char in normalized_text) or any(
            marker in lowered
            for marker in [
                "remote",
                "hybrid",
                "office",
                "b1",
                "b2",
                "c1",
                "c2",
                "a1",
                "a2",
                "native",
                "no live coding",
                "no take-home",
                "no take home",
                "paid take-home",
                "unpaid take-home",
            ]
        )
        if parsed and (
            has_explicit_update_markers or (has_specific_update_values and not has_feedback_markers)
        ):
            payload.update(
                {
                    "intent": "update_vacancy_preferences",
                    "response_text": "Got it. I can update this vacancy.",
                    "proposed_action": "update_vacancy_preferences",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "vacancy_open_update_preferences",
                }
            )
        elif has_feedback_markers:
            payload.update(
                {
                    "intent": "vacancy_feedback",
                    "response_text": "Got it. Tell me what keeps missing and I can save that feedback or turn it into a vacancy update.",
                    "proposed_action": "record_vacancy_feedback",
                    "answer_text": normalized_text,
                    "needs_follow_up": False,
                    "reason_code": "vacancy_open_feedback",
                }
            )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_vacancy_open_decision_v1",
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

    matching_hints: list[str] = []
    for item in recent_context or []:
        normalized_item = " ".join(str(item or "").split()).strip()
        if (
            normalized_item.startswith("Current matching blockers:")
            or normalized_item.startswith("Matching blocker snapshot:")
            or normalized_item.startswith("Recent matching feedback signal:")
        ):
            if normalized_item not in matching_hints:
                matching_hints.append(normalized_item)

    if any(token in text for token in ["hi", "hello", "hey", "thanks", "thank you"]):
        intent = "small_talk"
        reason_code = "small_talk_redirect"
        response_text = f"Happy to help. {context.guidance_text or response_text}"
    elif matching_hints and any(
        token in text
        for token in [
            "why no",
            "why not",
            "what is blocking",
            "what's blocking",
            "why am i not seeing",
            "why dont i see",
            "why don't i see",
            "почему нет",
            "почему не",
            "что мешает",
            "що заважає",
        ]
    ):
        intent = "support_request"
        reason_code = "matching_blocker_snapshot"
        response_text = " ".join(matching_hints[:3])
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


def safe_delete_confirmation_decision(
    session,
    *,
    latest_user_message: str,
    entity_label: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> LLMResult:
    normalized_text = (latest_user_message or "").strip()
    command = normalize_command_text(normalized_text)
    lowered = normalized_text.lower()
    if command in {
        "confirm delete",
        "confirm delete profile",
        "confirm delete vacancy",
        "delete profile",
        "delete vacancy",
    } or command in {"yes", "да", "подтверждаю", "подтвердить"}:
        return LLMResult(
            payload={
                "intent": "confirm",
                "response_text": f"Understood. I will delete the {entity_label} now.",
                "proposed_action": "confirm_delete",
                "keep_current_state": False,
                "needs_follow_up": False,
                "reason_code": "delete_confirmation_explicit_command",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_delete_confirmation_decision_v1",
        )
    if command in {"cancel delete", "keep profile", "keep vacancy", "don't delete", "dont delete", "нет", "no"}:
        return LLMResult(
            payload={
                "intent": "cancel",
                "response_text": f"Understood. I will keep the {entity_label} active.",
                "proposed_action": "cancel_delete",
                "keep_current_state": False,
                "needs_follow_up": False,
                "reason_code": "delete_confirmation_cancel_command",
            },
            model_name="baseline-deterministic",
            prompt_version="baseline_delete_confirmation_decision_v1",
        )

    if should_use_llm_runtime(session):
        try:
            return delete_confirmation_decision_with_llm(
                latest_user_message=latest_user_message,
                entity_label=entity_label,
                current_step_guidance=current_step_guidance,
                recent_context=recent_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("delete_confirmation_decision_fallback", error=str(exc))

    payload = {
        "intent": "help",
        "response_text": current_step_guidance or f"Review the deletion details for this {entity_label} and either confirm or cancel.",
        "proposed_action": None,
        "keep_current_state": True,
        "needs_follow_up": True,
        "reason_code": "delete_confirmation_help_fallback",
    }
    if command in {"confirm delete", "confirm delete profile", "confirm delete vacancy"}:
        payload.update(
            {
                "intent": "confirm",
                "response_text": f"Understood. I will delete the {entity_label} now.",
                "proposed_action": "confirm_delete",
                "needs_follow_up": False,
                "reason_code": "delete_confirmation_confirm",
            }
        )
    elif command in {"cancel delete", "keep profile", "keep vacancy", "don't delete", "dont delete"}:
        payload.update(
            {
                "intent": "cancel",
                "response_text": f"Understood. I will keep the {entity_label} active.",
                "proposed_action": "cancel_delete",
                "needs_follow_up": False,
                "reason_code": "delete_confirmation_cancel",
            }
        )
    elif any(token in lowered for token in ["what happens", "what exactly", "what will be cancelled", "can i cancel", "how do i cancel", "undo", "why", "help", "?"]):
        payload.update(
            {
                "intent": "help",
                "response_text": current_step_guidance or f"Review the deletion details for this {entity_label} and either confirm or cancel.",
                "needs_follow_up": True,
                "reason_code": "delete_confirmation_help_question",
            }
        )
    return LLMResult(
        payload=payload,
        model_name="baseline-deterministic",
        prompt_version="baseline_delete_confirmation_decision_v1",
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


def safe_rerank_candidates(session, *, vacancy, vacancy_context: dict | None = None, shortlisted_candidates: list[dict]) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            result = rerank_candidates_with_llm(
                vacancy=vacancy,
                vacancy_context=vacancy_context,
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
        matched_signals, concerns = _baseline_rerank_signals(item)
        ranked.append(
            {
                "candidate_ref": item["candidate_ref"],
                "rank": rank,
                "fit_score": round(float(item.get("deterministic_score") or 0.0), 4),
                "rationale": "Strong deterministic fit based on stack overlap, experience, and seniority alignment.",
                "matched_signals": matched_signals,
                "concerns": concerns,
            }
        )
    return LLMResult(
        payload={"ranked_candidates": ranked},
        model_name="baseline-deterministic",
        prompt_version="baseline_candidate_rerank_v2",
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


def safe_build_match_card_copy(
    session,
    *,
    audience: str,
    role_title: str | None,
    candidate_name: str | None = None,
    candidate_summary: str | None = None,
    project_summary: str | None = None,
    fit_reason: str | None = None,
    compensation_details: str | None = None,
    process_details: str | None = None,
    fit_band_label: str | None = None,
    gap_context: str | None = None,
    action_hint: str | None = None,
    fallback_message: str,
) -> LLMResult:
    if should_use_llm_runtime(session):
        try:
            result = build_match_card_copy_with_llm(
                audience=audience,
                role_title=role_title,
                candidate_name=candidate_name,
                candidate_summary=candidate_summary,
                project_summary=project_summary,
                fit_reason=fit_reason,
                compensation_details=compensation_details,
                process_details=process_details,
                fit_band_label=fit_band_label,
                gap_context=gap_context,
                action_hint=action_hint,
            )
            message = str((result.payload or {}).get("message") or "").strip()
            if message:
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("match_card_copy_fallback_to_baseline", error=str(exc), audience=audience)
    return LLMResult(
        payload={"message": fallback_message[:700]},
        model_name="baseline-deterministic",
        prompt_version="baseline_match_card_copy_v1",
    )


def safe_build_deletion_confirmation(
    session,
    *,
    entity_type: str,
    entity_label: str | None = None,
    has_active_interview: bool,
    has_active_matches: bool,
) -> LLMResult:
    side_effects = []
    if has_active_matches:
        side_effects.append("remove you from active matching")
    if has_active_interview:
        side_effects.append("cancel the active interview")
    side_effects_text = ""
    if side_effects:
        side_effects_text = " It will also " + " and ".join(side_effects) + "."
    noun = "profile" if entity_type == "candidate_profile" else "vacancy"
    confirm_label = "Confirm delete profile" if noun == "profile" else "Confirm delete vacancy"
    entity_display = f' "{entity_label}"' if entity_label else ""
    baseline = LLMResult(
        payload={
            "message": f"Please confirm deletion of this {noun}{entity_display}. Tap '{confirm_label}' to continue or 'Cancel delete' to keep it.{side_effects_text}",
            "is_explicit_confirmation_required": True,
        },
        model_name="baseline-deterministic",
        prompt_version="baseline_deletion_confirmation_v1",
    )
    if should_use_llm_runtime(session):
        try:
            result = build_deletion_confirmation_with_llm(
                entity_type=entity_type,
                entity_label=entity_label,
                has_active_interview=has_active_interview,
                has_active_matches=has_active_matches,
            )
            message = str((result.payload or {}).get("message") or "")
            if entity_label and entity_label.lower() not in message.lower():
                return baseline
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("deletion_confirmation_fallback_to_baseline", error=str(exc))
    return baseline


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
        payload={"message": f"We found a strong-fit opportunity{role_text}. The next step is a short AI interview. Review the vacancy card below and use Accept interview or Skip opportunity."},
        model_name="baseline-deterministic",
        prompt_version="baseline_interview_invitation_copy_v1",
    )
