import re
from typing import Optional

from src.candidate_profile.question_parser import COUNTRY_CODES
from src.candidate_profile.summary_builder import KNOWN_SKILLS


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _extract_currency(text: str) -> Optional[str]:
    lowered = text.lower()
    if "$" in text or "usd" in lowered:
        return "USD"
    if "€" in text or "eur" in lowered:
        return "EUR"
    if "£" in text or "gbp" in lowered:
        return "GBP"
    return None


def _extract_period(text: str) -> Optional[str]:
    lowered = text.lower()
    if re.search(r"\b(per month|monthly|month)\b", lowered) or "/month" in lowered:
        return "month"
    if re.search(r"\b(per year|yearly|annual|annually|year)\b", lowered) or "/year" in lowered:
        return "year"
    return None


def _parse_amount(raw_value: str) -> Optional[float]:
    value = raw_value.replace(",", "").strip().lower()
    multiplier = 1
    if value.endswith("k"):
        multiplier = 1000
        value = value[:-1]
    try:
        return float(value) * multiplier
    except ValueError:
        return None


def parse_budget(text: str) -> dict:
    normalized = _normalize_text(text)
    budget_scope = normalized
    scope_match = re.search(
        r"(?:budget|salary|compensation)\s*:?\s*([^.;\n]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if scope_match is not None:
        budget_scope = scope_match.group(1)

    matches = re.findall(
        r"(?<![A-Za-z])(?:[$€£]\s*)?(\d{1,3}(?:[,\d]{0,3})?(?:\.\d+)?k?)(?![A-Za-z])",
        budget_scope,
        flags=re.IGNORECASE,
    )
    values = []
    for match in matches:
        amount = _parse_amount(match)
        if amount is not None:
            values.append(amount)
    if not values:
        return {}
    budget_min = min(values)
    budget_max = max(values) if len(values) > 1 else budget_min
    return {
        "budget_min": budget_min,
        "budget_max": budget_max,
        "budget_currency": _extract_currency(normalized),
        "budget_period": _extract_period(normalized),
    }


def parse_countries(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    found = []
    for country_name, code in COUNTRY_CODES.items():
        if country_name in lowered and code not in found:
            found.append(code)
    return {"countries_allowed_json": found} if found else {}


def parse_work_format(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    if "remote" in lowered:
        return {"work_format": "remote"}
    if "hybrid" in lowered:
        return {"work_format": "hybrid"}
    if "office" in lowered or "onsite" in lowered or "on-site" in lowered:
        return {"work_format": "office"}
    return {}


def parse_team_size(text: str) -> dict:
    normalized = _normalize_text(text).lower()
    match = re.search(r"(?:team size|team of|team)\s*:?\s*(\d{1,3})", normalized)
    if match is None:
        return {}
    return {"team_size": int(match.group(1))}


def parse_project_description(text: str) -> dict:
    normalized = _normalize_text(text)
    if re.search(r"https?://\S+|www\.\S+", normalized, flags=re.IGNORECASE):
        return {"project_description": normalized}
    match = re.search(r"(?:project|product|description)\s*:?\s*(.+)", normalized, flags=re.IGNORECASE)
    if match is not None:
        return {"project_description": match.group(1).strip()}
    if len(normalized.split()) >= 6 and not re.search(r"\b(remote|hybrid|office|usd|eur|gbp)\b", normalized, flags=re.IGNORECASE):
        return {"project_description": normalized}
    return {}


def parse_primary_tech_stack(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    found = []
    for skill in KNOWN_SKILLS:
        if skill in lowered:
            found.append(skill)
    return {"primary_tech_stack_json": found[:8]} if found else {}


def parse_role_title(text: str) -> dict:
    normalized = _normalize_text(text)
    match = re.search(r"(?:role|title|position)\s*:?\s*([^.;\n]+)", normalized, flags=re.IGNORECASE)
    if match is None:
        return {}
    return {"role_title": match.group(1).strip()}


def parse_seniority(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    if "senior" in lowered or "lead" in lowered or "staff" in lowered:
        return {"seniority_normalized": "senior"}
    if "middle" in lowered or "mid-level" in lowered:
        return {"seniority_normalized": "middle"}
    if "junior" in lowered:
        return {"seniority_normalized": "junior"}
    return {}


def parse_vacancy_clarifications(text: str) -> dict:
    normalized = _normalize_text(text)
    parsed = {}
    parsed.update(parse_role_title(normalized))
    parsed.update(parse_seniority(normalized))
    parsed.update(parse_budget(normalized))
    parsed.update(parse_countries(normalized))
    parsed.update(parse_work_format(normalized))
    parsed.update(parse_team_size(normalized))
    parsed.update(parse_project_description(normalized))
    parsed.update(parse_primary_tech_stack(normalized))
    return parsed
