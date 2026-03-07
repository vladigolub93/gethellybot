from src.notifications.rendering import render_notification_text


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
