from src.candidate_profile.summary_builder import (
    build_approval_summary_text,
    build_candidate_summary,
    extract_skills,
    extract_years_experience,
)


def test_extract_years_experience() -> None:
    assert extract_years_experience("Python backend engineer with 5 years of experience") == 5


def test_extract_skills() -> None:
    skills = extract_skills("Worked with Python, FastAPI, PostgreSQL, Redis and Docker")

    assert skills == ["python", "fastapi", "postgresql", "redis", "docker"]


def test_build_candidate_summary() -> None:
    summary = build_candidate_summary(
        "Senior Python engineer with 6 years experience building FastAPI and PostgreSQL systems.",
        "pasted_text",
    )

    assert summary["status"] == "draft"
    assert summary["years_experience"] == 6
    assert "python" in summary["skills"]
    assert summary["approval_summary_text"].startswith("You are a Senior Python engineer")
    assert summary["approval_summary_text"].count(".") == 3


def test_build_approval_summary_text_has_three_sentences() -> None:
    text = build_approval_summary_text(
        headline="Backend Engineer",
        source_text="Backend engineer with 5 years in fintech using Python and PostgreSQL.",
        years_experience=5,
        skills=["python", "postgresql"],
    )

    assert text.startswith("You are a Backend Engineer")
    assert text.count(".") == 3
