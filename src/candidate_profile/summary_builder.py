import re
from typing import List, Optional


KNOWN_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "node",
    "react",
    "vue",
    "angular",
    "django",
    "fastapi",
    "flask",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "aws",
    "gcp",
    "docker",
    "kubernetes",
]


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def extract_years_experience(text: str) -> Optional[int]:
    normalized = _normalize_text(text).lower()
    match = re.search(r"(\d{1,2})\+?\s*(?:years?|yrs?)", normalized)
    if match is None:
        return None
    return int(match.group(1))


def extract_skills(text: str) -> List[str]:
    normalized = _normalize_text(text).lower()
    found = []
    for skill in KNOWN_SKILLS:
        if skill in normalized:
            found.append(skill)
    return found


def build_candidate_summary(source_text: str, source_type: str) -> dict:
    normalized = _normalize_text(source_text)
    headline = normalized[:160].strip()
    if len(normalized) > 160 and " " in headline:
        headline = headline.rsplit(" ", 1)[0]

    return {
        "status": "draft",
        "source_type": source_type,
        "headline": headline,
        "experience_excerpt": normalized[:1200],
        "years_experience": extract_years_experience(normalized),
        "skills": extract_skills(normalized),
    }
