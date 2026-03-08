from src.notifications.rendering import (
    render_notification_reply_markup,
    render_notification_text,
)


def test_render_notification_with_summary_and_evaluation() -> None:
    rendered = render_notification_text(
        template_key="manager_candidate_review_ready",
        payload={
            "text": "Candidate is ready.",
            "candidate_summary": {
                "target_role": "Backend Engineer",
                "skills": ["python", "fastapi"],
            },
            "evaluation": {
                "final_score": 0.82,
                "recommendation": "advance",
            },
        },
    )

    assert "Candidate is ready." in rendered
    assert "Candidate:" in rendered
    assert "Target role: Backend Engineer" in rendered
    assert "Skills: python, fastapi" in rendered
    assert "Evaluation:" in rendered
    assert "Final score: 0.82" in rendered


def test_render_notification_falls_back_to_template_name() -> None:
    rendered = render_notification_text(template_key="empty_case", payload={})
    assert rendered == "Helly notification: empty_case"


def test_candidate_summary_review_prefers_candidate_facing_summary_text() -> None:
    rendered = render_notification_text(
        template_key="candidate_summary_ready_for_review",
        payload={
            "text": "Your profile summary is ready.",
            "summary": {
                "headline": "Senior Python backend engineer.",
                "skills": ["python", "fastapi"],
                "approval_summary_text": (
                    "You are Ivan, a Senior Backend Engineer with 6 years of experience building backend APIs. "
                    "You have strong hands-on experience with Python, FastAPI, and PostgreSQL. "
                    "You have worked on SaaS and internal platform products that support business-critical workflows."
                ),
            },
        },
    )

    assert "Your profile summary is ready." in rendered
    assert "You are Ivan, a Senior Backend Engineer" in rendered
    assert "Summary:" not in rendered
    assert "Headline:" not in rendered


def test_candidate_summary_review_does_not_render_internal_mapping_without_approval_text() -> None:
    rendered = render_notification_text(
        template_key="candidate_summary_ready_for_review",
        payload={
            "text": "Your profile summary is ready.",
            "summary": {
                "headline": "Senior Python backend engineer.",
                "experience_excerpt": "Worked on APIs and infrastructure.",
                "skills": ["python", "fastapi"],
            },
        },
    )

    assert rendered == "Your profile summary is ready."


def test_render_notification_reply_markup_returns_payload_markup() -> None:
    reply_markup = {
        "keyboard": [["Candidate", "Hiring Manager"]],
        "resize_keyboard": True,
    }

    rendered = render_notification_reply_markup(
        template_key="request_role",
        payload={"text": "Choose role", "reply_markup": reply_markup},
    )

    assert rendered == reply_markup
