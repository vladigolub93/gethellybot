import re
from typing import List, Optional

from src.candidate_profile.skills_inventory import extract_full_hard_skills

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
    return extract_full_hard_skills(text, limit=12)


def build_candidate_summary(source_text: str, source_type: str) -> dict:
    normalized = _normalize_text(source_text)
    headline = normalized[:160].strip()
    if len(normalized) > 160 and " " in headline:
        headline = headline.rsplit(" ", 1)[0]

    years_experience = extract_years_experience(normalized)
    skills = extract_skills(normalized)

    return {
        "status": "draft",
        "source_type": source_type,
        "headline": headline,
        "experience_excerpt": normalized[:1200],
        "years_experience": years_experience,
        "skills": skills,
        "approval_summary_text": build_approval_summary_text(
            headline=headline,
            source_text=normalized,
            years_experience=years_experience,
            skills=skills,
        ),
    }


def build_approval_summary_text(
    *,
    headline: str,
    source_text: str,
    years_experience: Optional[int],
    skills: List[str],
) -> str:
    role = headline.strip(" .,-") or "software professional"
    years_part = (
        f" with {years_experience}+ years of experience"
        if years_experience is not None
        else " with relevant professional experience"
    )

    if skills:
        if len(skills) == 1:
            skills_part = skills[0]
        elif len(skills) == 2:
            skills_part = f"{skills[0]} and {skills[1]}"
        else:
            skills_part = ", ".join(skills[:3])
        sentence_two = f"Your main technical strengths include {skills_part}."
    else:
        sentence_two = "Your background shows practical technical experience from the information provided."

    lowered = source_text.lower()
    domain_map = {
        "fintech": "fintech products",
        "saas": "SaaS products",
        "ecommerce": "e-commerce platforms",
        "e-commerce": "e-commerce platforms",
        "marketplace": "marketplace products",
        "healthcare": "healthcare products",
        "edtech": "edtech products",
        "ai": "AI-enabled products",
        "ml": "machine learning systems",
        "recruit": "recruiting products",
        "crm": "CRM systems",
    }
    matched_domains = []
    for token, label in domain_map.items():
        if token in lowered and label not in matched_domains:
            matched_domains.append(label)
    if matched_domains:
        if len(matched_domains) == 1:
            domain_part = matched_domains[0]
        else:
            domain_part = ", ".join(matched_domains[:2])
        sentence_three = f"You have worked on {domain_part} and related software systems."
    else:
        sentence_three = "You have worked on software systems and products described in your background."

    return f"You are a {role}{years_part}. {sentence_two} {sentence_three}"
