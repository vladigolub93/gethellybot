from __future__ import annotations

from copy import deepcopy


MAX_TELEGRAM_MESSAGE_CHARS = 900
SOFT_SPLIT_CHARS = 420


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _render_mapping(mapping: dict) -> list[str]:
    lines = []
    for key, value in mapping.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            rendered_value = ", ".join(str(item) for item in value)
        else:
            rendered_value = str(value)
        lines.append(f"{_humanize_key(key)}: {rendered_value}")
    return lines


def _append_section(lines: list[str], title: str, section_lines: list[str]) -> None:
    visible_lines = [line for line in section_lines if str(line).strip()]
    if not visible_lines:
        return
    lines.append("")
    lines.append(title)
    lines.extend(visible_lines)


def _render_counterparty(counterparty: dict) -> list[str]:
    lines = []
    name = counterparty.get("name")
    username = counterparty.get("username")
    phone_number = counterparty.get("phone_number")
    if name:
        lines.append(f"Name: {name}")
    if username:
        lines.append(f"Telegram username: @{username.lstrip('@')}")
    if phone_number:
        lines.append(f"Phone: {phone_number}")
    return lines


def _render_candidate_package(candidate_package: dict) -> list[str]:
    lines = ["Candidate package:"]
    name = candidate_package.get("candidate_name")
    role_title = candidate_package.get("vacancy_role_title")
    if name:
        lines.append(f"Candidate: {name}")
    if role_title:
        lines.append(f"Vacancy: {role_title}")
    summary_text = candidate_package.get("candidate_summary_text")
    if summary_text:
        lines.append("")
        lines.append("Profile summary:")
        lines.append(str(summary_text))
    skills = candidate_package.get("skills") or []
    if skills:
        lines.append("")
        lines.append(f"Skills: {', '.join(str(item) for item in skills)}")
    work_preferences = candidate_package.get("work_preferences") or []
    if work_preferences:
        lines.append("")
        lines.append("Work preferences:")
        lines.extend(str(item) for item in work_preferences)
    verification_status = candidate_package.get("verification_status")
    if verification_status:
        lines.append("")
        lines.append(f"Verification: {verification_status}")
    interview_summary = candidate_package.get("interview_summary")
    if interview_summary:
        lines.append("")
        lines.append("Interview summary:")
        lines.append(str(interview_summary))
    strengths = candidate_package.get("strengths") or []
    if strengths:
        lines.append("")
        lines.append("Strengths:")
        lines.extend(f"- {item}" for item in strengths)
    risks = candidate_package.get("risks") or []
    if risks:
        lines.append("")
        lines.append("Risks:")
        lines.extend(f"- {item}" for item in risks)
    recommendation = candidate_package.get("recommendation")
    final_score = candidate_package.get("final_score")
    if recommendation or final_score is not None:
        lines.append("")
        if recommendation:
            lines.append(f"Recommendation: {recommendation}")
        if final_score is not None:
            lines.append(f"Final score: {final_score}")
    return lines


def _render_vacancy_package(vacancy_package: dict) -> list[str]:
    lines = ["Vacancy package:"]
    role_title = vacancy_package.get("vacancy_role_title")
    if role_title:
        lines.append(f"Role: {role_title}")
    summary_text = vacancy_package.get("vacancy_summary_text")
    if summary_text:
        lines.append("")
        lines.append("Role summary:")
        lines.append(str(summary_text))
    stack = vacancy_package.get("stack") or []
    if stack:
        lines.append("")
        lines.append(f"Stack: {', '.join(str(item) for item in stack)}")
    work_details = vacancy_package.get("work_details") or []
    if work_details:
        lines.append("")
        lines.append("Work details:")
        lines.extend(str(item) for item in work_details)
    project_description = vacancy_package.get("project_description")
    if project_description:
        lines.append("")
        lines.append("Project:")
        lines.append(str(project_description))
    return lines


def render_notification_text(*, template_key: str, payload: dict) -> str:
    lines = []
    text = (payload or {}).get("text")
    if text:
        lines.append(str(text).strip())

    summary = (payload or {}).get("summary")
    if (
        template_key == "candidate_summary_ready_for_review"
        and isinstance(summary, dict)
        and summary.get("approval_summary_text")
    ):
        lines.append("")
        lines.append(str(summary.get("approval_summary_text")).strip())
    elif template_key == "candidate_summary_ready_for_review":
        pass
    elif (
        template_key == "vacancy_summary_ready_for_review"
        and isinstance(summary, dict)
        and summary.get("approval_summary_text")
    ):
        lines.append("")
        lines.append(str(summary.get("approval_summary_text")).strip())
    elif template_key == "vacancy_summary_ready_for_review":
        pass
    elif isinstance(summary, dict) and summary:
        _append_section(lines, "Summary:", _render_mapping(summary))

    evaluation = (payload or {}).get("evaluation")
    if isinstance(evaluation, dict) and evaluation:
        _append_section(lines, "Evaluation:", _render_mapping(evaluation))

    candidate_package = (payload or {}).get("candidate_package")
    if isinstance(candidate_package, dict) and candidate_package:
        lines.append("")
        lines.extend(_render_candidate_package(candidate_package))

    vacancy_package = (payload or {}).get("vacancy_package")
    if isinstance(vacancy_package, dict) and vacancy_package:
        lines.append("")
        lines.extend(_render_vacancy_package(vacancy_package))

    candidate_summary = (payload or {}).get("candidate_summary")
    if isinstance(candidate_summary, dict) and candidate_summary:
        _append_section(lines, "Candidate:", _render_mapping(candidate_summary))

    counterparty = (payload or {}).get("counterparty")
    if isinstance(counterparty, dict) and counterparty:
        _append_section(lines, "Contact details:", _render_counterparty(counterparty))

    inconsistencies = (payload or {}).get("inconsistencies")
    if isinstance(inconsistencies, dict) and inconsistencies:
        _append_section(lines, "Inconsistencies:", _render_mapping(inconsistencies))

    rendered = "\n".join(lines).strip()
    if not rendered:
        rendered = f"Helly notification: {template_key}"
    return rendered[:3900]


def render_notification_messages(*, template_key: str, payload: dict) -> list[str]:
    payload = payload or {}
    explicit_messages = [
        str(item).strip()
        for item in (payload.get("messages") or [])
        if str(item).strip()
    ]
    if explicit_messages:
        remaining_payload = deepcopy(payload)
        remaining_payload.pop("messages", None)
        remaining_payload.pop("text", None)
        remainder = render_notification_text(template_key=template_key, payload=remaining_payload)
        if remainder and remainder != f"Helly notification: {template_key}":
            explicit_messages.append(remainder)
        return explicit_messages

    rendered = render_notification_text(template_key=template_key, payload=payload)
    paragraphs = [part.strip() for part in rendered.split("\n\n") if part.strip()]
    if not paragraphs:
        return [rendered]
    if len(rendered) <= SOFT_SPLIT_CHARS and len(paragraphs) <= 2:
        return [rendered]
    if len(rendered) <= MAX_TELEGRAM_MESSAGE_CHARS and len(paragraphs) <= 2:
        return [rendered]
    target_limit = (
        SOFT_SPLIT_CHARS
        if len(rendered) > SOFT_SPLIT_CHARS and len(paragraphs) > 2
        else MAX_TELEGRAM_MESSAGE_CHARS
    )

    messages: list[str] = []
    current_parts: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        separator_length = 2 if current_parts else 0
        projected_length = current_length + separator_length + paragraph_length

        if current_parts and projected_length > target_limit:
            messages.append("\n\n".join(current_parts).strip())
            current_parts = [paragraph]
            current_length = paragraph_length
            continue

        current_parts.append(paragraph)
        current_length = projected_length

    if current_parts:
        messages.append("\n\n".join(current_parts).strip())

    return messages or [rendered]


def render_notification_reply_markup(*, template_key: str, payload: dict):
    return (payload or {}).get("reply_markup")
