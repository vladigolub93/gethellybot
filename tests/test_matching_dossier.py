from __future__ import annotations

from types import SimpleNamespace

from src.matching.dossier import (
    build_candidate_review_dossier,
    build_manager_review_dossier,
)


def test_build_candidate_review_dossier_includes_team_size_and_source_excerpts() -> None:
    vacancy = SimpleNamespace(
        role_title="Senior Backend Engineer",
        seniority_normalized="senior",
        budget_min=6000,
        budget_max=7000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        office_city=None,
        countries_allowed_json=["UA", "PL"],
        required_english_level="b2",
        team_size=8,
        project_description="Marketplace platform for analytics and pricing automation.",
        primary_tech_stack_json=["Node.js", "Redis", "GCP"],
        hiring_stages_json=["technical_interview", "take_home"],
        has_take_home_task=True,
        take_home_paid=False,
        has_live_coding=False,
    )
    vacancy_version = SimpleNamespace(
        approval_summary_text="Backend role for a marketplace analytics product.",
        summary_json={"project_description_excerpt": "Marketplace analytics product."},
        extracted_text="Full JD text about the backend team and collaboration model.",
        transcript_text=None,
    )
    match = SimpleNamespace(
        status="candidate_decision_pending",
        rationale_json={
            "fit_band": "strong",
            "matched_signals": ["Backend overlap", "Node.js experience"],
            "gap_signals": ["No direct pricing background"],
        },
    )

    dossier = build_candidate_review_dossier(
        match=match,
        vacancy=vacancy,
        vacancy_version=vacancy_version,
    )

    assert dossier["vacancy"]["team_size"] == 8
    assert "Node.js" in dossier["vacancy"]["primary_tech_stack"]
    assert dossier["vacancy_summary"]["approval_summary_text"] == "Backend role for a marketplace analytics product."
    assert "backend team" in dossier["source_excerpts"]["extracted_text_excerpt"]


def test_build_manager_review_dossier_includes_verification_and_evaluation() -> None:
    candidate = SimpleNamespace(
        target_role="Backend Engineer",
        seniority_normalized="senior",
        salary_min=5000,
        salary_max=6000,
        salary_currency="USD",
        salary_period="month",
        location_text="Kyiv, Ukraine",
        country_code="UA",
        city="Kyiv",
        work_formats_json=["remote", "hybrid"],
        work_format=None,
        english_level="b2",
        preferred_domains_json=["fintech", "saas"],
        show_take_home_task_roles=False,
        show_live_coding_roles=True,
    )
    candidate_version = SimpleNamespace(
        summary_json={
            "headline": "Senior backend engineer",
            "experience_excerpt": "Built APIs and data systems.",
            "approval_summary_text": "Senior backend engineer with API and platform experience.",
            "years_experience": 6,
            "skills": ["Python", "Node.js", "Redis"],
        },
        extracted_text="Resume with backend platform and API work.",
        transcript_text=None,
    )
    vacancy = SimpleNamespace(role_title="Node.js Developer")
    match = SimpleNamespace(
        status="manager_decision_pending",
        rationale_json={
            "fit_band": "medium",
            "matched_signals": ["Strong backend overlap"],
            "gap_signals": ["Primary stack is more Python-heavy"],
        },
    )
    latest_verification = SimpleNamespace(
        status="submitted",
        attempt_no=1,
        submitted_at="2026-03-19 12:00:00+00:00",
    )
    evaluation_result = SimpleNamespace(
        status="completed",
        final_score=0.82,
        recommendation="strong_yes",
        strengths_json=["Clear ownership", "Strong backend depth"],
        risks_json=["Less direct Node.js time"],
    )

    dossier = build_manager_review_dossier(
        match=match,
        vacancy=vacancy,
        candidate=candidate,
        candidate_version=candidate_version,
        latest_verification=latest_verification,
        evaluation_result=evaluation_result,
    )

    assert dossier["candidate"]["work_formats"] == "remote + hybrid"
    assert dossier["verification"]["latest_submitted_status"] == "submitted"
    assert dossier["evaluation"]["recommendation"] == "strong_yes"
    assert "Python" in dossier["candidate_summary"]["skills"]
