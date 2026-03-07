from __future__ import annotations


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
    elif isinstance(summary, dict) and summary:
        lines.append("")
        lines.append("Summary:")
        lines.extend(_render_mapping(summary))

    evaluation = (payload or {}).get("evaluation")
    if isinstance(evaluation, dict) and evaluation:
        lines.append("")
        lines.append("Evaluation:")
        lines.extend(_render_mapping(evaluation))

    candidate_summary = (payload or {}).get("candidate_summary")
    if isinstance(candidate_summary, dict) and candidate_summary:
        lines.append("")
        lines.append("Candidate:")
        lines.extend(_render_mapping(candidate_summary))

    inconsistencies = (payload or {}).get("inconsistencies")
    if isinstance(inconsistencies, dict) and inconsistencies:
        lines.append("")
        lines.append("Inconsistencies:")
        lines.extend(_render_mapping(inconsistencies))

    rendered = "\n".join(lines).strip()
    if not rendered:
        rendered = f"Helly notification: {template_key}"
    return rendered[:3900]


def render_notification_reply_markup(*, template_key: str, payload: dict):
    return (payload or {}).get("reply_markup")
