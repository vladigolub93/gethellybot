import re
from typing import Optional


COUNTRY_CODES = {
    "ukraine": "UA",
    "poland": "PL",
    "germany": "DE",
    "spain": "ES",
    "portugal": "PT",
    "france": "FR",
    "italy": "IT",
    "netherlands": "NL",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "usa": "US",
    "canada": "CA",
}


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _extract_currency(text: str) -> Optional[str]:
    lowered = text.lower()
    if "$" in text or "usd" in lowered or "dollar" in lowered:
        return "USD"
    if "€" in text or "eur" in lowered or "euro" in lowered:
        return "EUR"
    if "£" in text or "gbp" in lowered or "pound" in lowered:
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


def parse_salary_expectations(text: str) -> dict:
    normalized = _normalize_text(text)
    matches = re.findall(r"(?<!\d)(\d{1,3}(?:[,\d]{0,3})?(?:\.\d+)?k?)(?!\d)", normalized, flags=re.IGNORECASE)
    values = []
    for match in matches:
        amount = _parse_amount(match)
        if amount is not None:
            values.append(amount)

    if not values:
        return {}

    salary_min = min(values)
    salary_max = max(values)
    if len(values) == 1:
        salary_max = salary_min

    return {
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": _extract_currency(normalized),
        "salary_period": _extract_period(normalized),
    }


def parse_work_format(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    if "remote" in lowered:
        return {"work_format": "remote"}
    if "hybrid" in lowered:
        return {"work_format": "hybrid"}
    if "office" in lowered or "onsite" in lowered or "on-site" in lowered:
        return {"work_format": "office"}
    return {}


def _extract_labeled_value(text: str, label: str) -> Optional[str]:
    pattern = rf"{label}\s*:\s*([^.;\n]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return _normalize_text(match.group(1))


def parse_location(text: str) -> dict:
    normalized = _normalize_text(text)
    location_text = (
        _extract_labeled_value(normalized, "location")
        or _extract_labeled_value(normalized, "based in")
        or _extract_labeled_value(normalized, "located in")
    )
    if location_text is None:
        lowered = normalized.lower()
        for marker in ("based in ", "located in ", "from ", "in "):
            if marker in lowered:
                start = lowered.index(marker) + len(marker)
                location_text = normalized[start:].strip(" .")
                break

    if not location_text:
        return {}

    location_text = re.split(
        r"\s+(?:and|but)\s+(?:open|prefer|preferred|remote|hybrid|office|onsite|on-site)\b",
        location_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,")

    parts = [part.strip() for part in location_text.split(",") if part.strip()]
    city = parts[0] if parts else None
    country_code = None
    lowered_location = location_text.lower()
    for country_name, code in COUNTRY_CODES.items():
        if country_name in lowered_location:
            country_code = code
            break

    return {
        "location_text": location_text,
        "city": city,
        "country_code": country_code,
    }


def parse_candidate_questions(text: str) -> dict:
    normalized = _normalize_text(text)
    parsed = {}
    parsed.update(parse_salary_expectations(normalized))
    parsed.update(parse_location(normalized))
    parsed.update(parse_work_format(normalized))
    return parsed
