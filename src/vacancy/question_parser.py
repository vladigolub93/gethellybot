from __future__ import annotations

import re
from typing import Optional

from src.candidate_profile.question_parser import COUNTRY_CODES
from src.candidate_profile.summary_builder import KNOWN_SKILLS
from src.shared.hiring_taxonomy import extract_hiring_stages, normalize_english_level


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


def parse_office_city(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    patterns = (
        r"(?:office city|office location|hybrid city|location)\s*:?\s*([^.;\n]+)",
        r"(?:office in|hybrid in|onsite in|on-site in)\s+([^.;\n]+)",
    )
    office_value = None
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match is not None:
            office_value = match.group(1).strip()
            break
    if office_value is None and any(token in lowered for token in ("office", "hybrid", "onsite", "on-site")):
        for country_name in COUNTRY_CODES:
            if country_name in lowered:
                office_value = normalized[: lowered.index(country_name)].strip(" ,.")
                break
    if not office_value:
        return {}
    office_city = office_value.split(",", 1)[0].strip(" .,-")
    return {"office_city": office_city} if office_city else {}


def parse_required_english_level(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    explicit_match = re.search(
        r"\b(?:english|eng)\s*(?:level)?\s*[:\-]?\s*(a1|a2|b1|b2|c1|c2|native)\b",
        lowered,
    )
    candidate = explicit_match.group(1) if explicit_match is not None else None
    if candidate is None:
        for token in (
            "native",
            "c2",
            "c1",
            "b2",
            "b1",
            "a2",
            "a1",
            "upper-intermediate",
            "upper intermediate",
            "intermediate",
            "advanced",
            "fluent",
        ):
            if token in lowered:
                candidate = token
                break
    english_level = normalize_english_level(candidate)
    return {"required_english_level": english_level} if english_level else {}


def parse_team_size(text: str) -> dict:
    normalized = _normalize_text(text).lower()
    match = re.search(r"(?:team size|team of|team)\s*:?\s*(\d{1,3})", normalized)
    if match is None:
        return {}
    return {"team_size": int(match.group(1))}


def parse_hiring_stages(text: str) -> dict:
    stages = extract_hiring_stages(text)
    return {"hiring_stages_json": stages} if stages else {}


def _parse_keyword_boolean(text: str, *, keywords: tuple[str, ...]) -> Optional[bool]:
    lowered = _normalize_text(text).lower()
    if any(keyword in lowered for keyword in keywords):
        if re.search(r"\b(no|not|without|none)\b", lowered):
            return False
        if re.search(r"\b(yes|yeah|yep|has|with|include|included|there is|there are|will be)\b", lowered):
            return True
        return True
    return None


def _extract_local_boolean(text: str, *, keywords: tuple[str, ...]) -> Optional[bool]:
    lowered = _normalize_text(text).lower()
    keyword_patterns = tuple(re.escape(keyword) for keyword in keywords)
    clauses = [
        clause.strip()
        for clause in re.split(r"[.;\n,]|\bbut\b|\bhowever\b", lowered)
        if clause.strip()
    ]
    relevant_clauses = [clause for clause in clauses if any(keyword in clause for keyword in keywords)]
    for clause in relevant_clauses:
        if re.search(r"\b(no|not|without|none)\b", clause):
            return False
        if re.search(r"\b(yes|yeah|yep|has|with|include|included|there is|there are|will be)\b", clause):
            return True

    positive_patterns = (
        rf"\b(?:yes|yeah|yep|has|with|include|included|there is|there are|will be)\b[^.!?\n]{{0,48}}\b(?:{'|'.join(keyword_patterns)})\b",
        rf"\b(?:{'|'.join(keyword_patterns)})\b[^.!?\n]{{0,48}}\b(?:yes|yeah|yep|has|with|include|included|there is|there are|will be)\b",
    )
    for pattern in positive_patterns:
        if re.search(pattern, lowered):
            return True

    negative_patterns = (
        rf"\b(?:no|not|without|none)\b[^.!?\n]{{0,48}}\b(?:{'|'.join(keyword_patterns)})\b",
        rf"\b(?:{'|'.join(keyword_patterns)})\b[^.!?\n]{{0,48}}\b(?:no|not|without|none)\b",
    )
    for pattern in negative_patterns:
        if re.search(pattern, lowered):
            return False

    if "both" in lowered and any(keyword in lowered for keyword in keywords):
        return True
    if "neither" in lowered and any(keyword in lowered for keyword in keywords):
        return False
    return _parse_keyword_boolean(lowered, keywords=keywords)


def parse_assessment_requirements(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    payload = {}
    take_home = _extract_local_boolean(
        lowered,
        keywords=("test task", "take home", "take-home", "home assignment"),
    )
    live_coding = _extract_local_boolean(
        lowered,
        keywords=("live coding", "live-coding", "pair programming", "coding interview"),
    )
    if take_home is not None:
        payload["has_take_home_task"] = take_home
    if live_coding is not None:
        payload["has_live_coding"] = live_coding
    if take_home:
        if re.search(r"\b(paid|compensated|we pay|will pay)\b", lowered):
            payload["take_home_paid"] = True
        elif re.search(r"\b(unpaid|not paid|without pay|free)\b", lowered):
            payload["take_home_paid"] = False
    return payload


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
    parsed.update(parse_work_format(normalized))
    parsed.update(parse_office_city(normalized))
    parsed.update(parse_countries(normalized))
    parsed.update(parse_required_english_level(normalized))
    parsed.update(parse_assessment_requirements(normalized))
    parsed.update(parse_hiring_stages(normalized))
    hiring_stages = list(parsed.get("hiring_stages_json") or [])
    if parsed.get("has_take_home_task") is False:
        hiring_stages = [stage for stage in hiring_stages if stage != "take_home"]
    elif parsed.get("has_take_home_task") is True and "take_home" not in hiring_stages:
        hiring_stages.append("take_home")
    if parsed.get("has_live_coding") is False:
        hiring_stages = [stage for stage in hiring_stages if stage != "live_coding"]
    elif parsed.get("has_live_coding") is True and "live_coding" not in hiring_stages:
        hiring_stages.append("live_coding")
    if hiring_stages:
        parsed["hiring_stages_json"] = hiring_stages
    parsed.update(parse_team_size(normalized))
    parsed.update(parse_project_description(normalized))
    parsed.update(parse_primary_tech_stack(normalized))
    return parsed
