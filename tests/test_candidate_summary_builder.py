from src.candidate_profile.summary_builder import (
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
