from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional


MATCH_STATUS_LABELS = {
    "shortlisted": "Matched",
    "manager_decision_pending": "Waiting for manager review",
    "candidate_applied": "Waiting for manager reply",
    "candidate_decision_pending": "Waiting for your reply",
    "manager_interview_requested": "Manager approved, waiting for candidate",
    "interview_queued": "Interview queued",
    "invited": "Interview invited",
    "accepted": "Interview accepted",
    "interview_completed": "Interview completed",
    "manager_review": "Manager review",
    "approved": "Contacts shared",
    "rejected": "Rejected",
    "manager_skipped": "Skipped by manager",
    "candidate_skipped": "Skipped by candidate",
    "candidate_declined_interview": "Candidate declined interview",
    "filtered_out": "Filtered out",
    "expired": "Expired",
}

INTERVIEW_STATE_LABELS = {
    "CREATED": "Prepared",
    "INVITED": "Invited",
    "ACCEPTED": "Accepted",
    "IN_PROGRESS": "In progress",
    "COMPLETED": "Completed",
}


def isoformat_or_none(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def format_money_range(min_value, max_value, currency, period) -> Optional[str]:
    bits: List[str] = []
    if min_value is not None and max_value is not None:
        bits.append("{min_value}-{max_value}".format(
            min_value=_format_money_number(min_value),
            max_value=_format_money_number(max_value),
        ))
    elif min_value is not None:
        bits.append(_format_money_number(min_value))
    elif max_value is not None:
        bits.append(_format_money_number(max_value))

    if currency:
        bits.append(str(currency))
    if period:
        bits.append("per {period}".format(period=period))
    rendered = " ".join(bit for bit in bits if bit).strip()
    return rendered or None


def _format_money_number(value) -> str:
    if isinstance(value, Decimal):
        if value == value.to_integral():
            return str(int(value))
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


def clean_list(values: Iterable[Any], limit: Optional[int] = None) -> List[str]:
    result = []
    for value in values or []:
        text = " ".join(str(value).split()).strip()
        if text:
            result.append(text)
        if limit and len(result) >= limit:
            break
    return result


def candidate_summary_snapshot(summary_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summary_json or {}
    return {
        "headline": summary.get("headline"),
        "approvalSummaryText": summary.get("approval_summary_text"),
        "skills": clean_list(summary.get("skills"), limit=12),
        "yearsExperience": summary.get("years_experience"),
        "targetRole": summary.get("target_role"),
    }


def vacancy_summary_snapshot(summary_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summary_json or {}
    return {
        "approvalSummaryText": summary.get("approval_summary_text"),
        "headline": summary.get("headline"),
        "skills": clean_list(summary.get("skills"), limit=12),
    }


def evaluation_snapshot(evaluation) -> Dict[str, Any]:
    report = getattr(evaluation, "report_json", None) or {}
    return {
        "status": getattr(evaluation, "status", None),
        "interviewSummary": report.get("interview_summary"),
        "strengths": clean_list(report.get("strengths") or getattr(evaluation, "strengths_json", None), limit=8),
        "risks": clean_list(report.get("risks") or getattr(evaluation, "risks_json", None), limit=8),
        "recommendation": report.get("recommendation") or getattr(evaluation, "recommendation", None),
        "finalScore": getattr(evaluation, "final_score", None),
    }


def match_status_label(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    return MATCH_STATUS_LABELS.get(status, status.replace("_", " ").title())


def interview_state_label(state: Optional[str]) -> Optional[str]:
    if state is None:
        return None
    return INTERVIEW_STATE_LABELS.get(state, state.replace("_", " ").title())
