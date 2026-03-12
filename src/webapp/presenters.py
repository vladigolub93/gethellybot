from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from src.candidate_profile.skills_inventory import display_skill_list


MATCH_STATUS_LABELS = {
    "shortlisted": "Matched",
    "manager_decision_pending": "Manager review",
    "candidate_applied": "Manager reply",
    "candidate_decision_pending": "Candidate reply",
    "manager_interview_requested": "Interview reply",
    "interview_queued": "Interview queued",
    "invited": "Interview invite",
    "accepted": "Interview accepted",
    "interview_completed": "Interview completed",
    "manager_review": "Under review",
    "approved": "Connected",
    "rejected": "Rejected",
    "manager_skipped": "Skipped",
    "candidate_skipped": "Skipped",
    "candidate_declined_interview": "Interview declined",
    "filtered_out": "Filtered out",
    "expired": "Expired",
}

MATCH_STATUS_LABELS_BY_PERSPECTIVE = {
    "candidate": {
        "candidate_decision_pending": "Your reply",
        "candidate_applied": "Manager reply",
        "manager_interview_requested": "Interview reply",
    },
    "manager": {
        "manager_decision_pending": "Your review",
        "candidate_applied": "Your reply",
        "candidate_decision_pending": "Candidate reply",
        "manager_interview_requested": "Candidate reply",
        "invited": "Candidate reply",
    },
}

MATCH_STATUS_DESCRIPTIONS = {
    "shortlisted": "Helly found a promising match between this candidate and this role.",
    "manager_decision_pending": "The hiring manager is reviewing this match now.",
    "candidate_applied": "The candidate already replied. The manager has the next move.",
    "candidate_decision_pending": "A candidate reply is needed before this match can move forward.",
    "manager_interview_requested": "The next interview step is ready, but a candidate reply is still needed.",
    "interview_queued": "The interview is being prepared and scheduling is in progress.",
    "invited": "An interview invite was sent and is waiting for a response.",
    "accepted": "The interview invite was accepted and the session can move forward.",
    "interview_completed": "The interview finished and the result is ready for review.",
    "manager_review": "This match is still under manager review.",
    "approved": "Contacts were shared and this match moved into direct communication.",
    "rejected": "This match was closed and will not continue.",
    "manager_skipped": "The manager chose not to continue with this match.",
    "candidate_skipped": "The candidate chose not to continue with this match.",
    "candidate_declined_interview": "The candidate declined the interview step.",
    "filtered_out": "This match was filtered out and is no longer active.",
    "expired": "This match expired without the next step being completed.",
}

MATCH_STATUS_DESCRIPTIONS_BY_PERSPECTIVE = {
    "candidate": {
        "manager_decision_pending": "Your profile is with the hiring manager. You are waiting for their review.",
        "candidate_applied": "You already replied. The manager has the next move.",
        "candidate_decision_pending": "Your reply is needed to keep this opportunity moving.",
        "manager_interview_requested": "The manager approved the next step. Your reply is needed before the interview moves forward.",
        "invited": "An interview invite was sent. Please respond to continue.",
        "approved": "Your contact details were shared and the role moved into direct communication.",
    },
    "manager": {
        "manager_decision_pending": "This candidate is waiting for your review.",
        "candidate_applied": "The candidate already replied. Your decision is needed now.",
        "candidate_decision_pending": "The candidate still needs to reply before this match can continue.",
        "manager_interview_requested": "You approved the next step. The candidate still needs to reply.",
        "invited": "An interview invite was sent. The candidate still needs to respond.",
        "approved": "Contacts were shared and this candidate moved into direct communication.",
        "interview_completed": "The interview is complete and ready for your review.",
    },
}

MATCH_ACTION_STATUSES_BY_PERSPECTIVE = {
    "candidate": frozenset({"candidate_decision_pending", "manager_interview_requested", "invited"}),
    "manager": frozenset({"manager_decision_pending", "candidate_applied", "interview_completed"}),
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


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    return text or None


def candidate_summary_snapshot(summary_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summary_json or {}
    return {
        "headline": summary.get("headline"),
        "approvalSummaryText": summary.get("approval_summary_text"),
        "skills": display_skill_list(summary.get("skills"), limit=12),
        "yearsExperience": summary.get("years_experience"),
        "targetRole": summary.get("target_role"),
        "experienceExcerpt": clean_text(summary.get("experience_excerpt")),
    }


def vacancy_summary_snapshot(summary_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summary_json or {}
    return {
        "approvalSummaryText": summary.get("approval_summary_text"),
        "headline": summary.get("headline"),
        "skills": display_skill_list(summary.get("skills"), limit=12),
        "projectDescriptionExcerpt": clean_text(summary.get("project_description_excerpt")),
    }


def source_text_snapshot(version) -> Dict[str, Any]:
    extracted_text = clean_text(getattr(version, "extracted_text", None))
    transcript_text = clean_text(getattr(version, "transcript_text", None))
    return {
        "sourceType": getattr(version, "source_type", None),
        "text": extracted_text or transcript_text,
        "extractedText": extracted_text,
        "transcriptText": transcript_text,
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


def match_status_label(status: Optional[str], perspective: str = "generic") -> Optional[str]:
    if status is None:
        return None
    return (
        MATCH_STATUS_LABELS_BY_PERSPECTIVE.get(perspective, {}).get(status)
        or MATCH_STATUS_LABELS.get(status)
        or status.replace("_", " ").title()
    )


def match_status_description(status: Optional[str], perspective: str = "generic") -> Optional[str]:
    if status is None:
        return None
    return (
        MATCH_STATUS_DESCRIPTIONS_BY_PERSPECTIVE.get(perspective, {}).get(status)
        or MATCH_STATUS_DESCRIPTIONS.get(status)
        or match_status_label(status, perspective)
    )


def match_requires_action(status: Optional[str], perspective: str = "generic") -> bool:
    if status is None:
        return False
    return status in MATCH_ACTION_STATUSES_BY_PERSPECTIVE.get(perspective, frozenset())


def interview_state_label(state: Optional[str]) -> Optional[str]:
    if state is None:
        return None
    return INTERVIEW_STATE_LABELS.get(state, state.replace("_", " ").title())
