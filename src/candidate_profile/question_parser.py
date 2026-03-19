from __future__ import annotations

import re
from typing import Optional

from src.candidate_profile.work_formats import parse_work_formats
from src.shared.hiring_taxonomy import extract_domains, normalize_english_level


COUNTRY_CODES = {
    "ukraine": "UA",
    "украина": "UA",
    "україна": "UA",
    "poland": "PL",
    "польша": "PL",
    "польща": "PL",
    "germany": "DE",
    "германия": "DE",
    "німеччина": "DE",
    "spain": "ES",
    "испания": "ES",
    "іспанія": "ES",
    "portugal": "PT",
    "португалия": "PT",
    "португалія": "PT",
    "france": "FR",
    "франция": "FR",
    "франція": "FR",
    "italy": "IT",
    "италия": "IT",
    "італія": "IT",
    "netherlands": "NL",
    "нидерланды": "NL",
    "нідерланди": "NL",
    "united kingdom": "GB",
    "uk": "GB",
    "великобритания": "GB",
    "велика британія": "GB",
    "united states": "US",
    "usa": "US",
    "сша": "US",
    "сполучені штати": "US",
    "canada": "CA",
    "канада": "CA",
}

_NEGATIVE_WORDS = r"(?:no|not|don't|do not|avoid|hide|skip|without|не|без|не хочу|не хочу бачити|не хочу видеть|не подходит|не підходить|не показувати|не показывать|уникати)"
_POSITIVE_WORDS = r"(?:yes|yeah|yep|ok|okay|fine|show|include|open to|can do|comfortable|fine with|так|ок|окей|підходить|подходит|можно|можна|готов|готова|готовий|готова)"
_CLAUSE_SPLIT_RE = r"[.;\n,]|\bbut\b|\bhowever\b|\bале\b|\bно\b|\bоднак\b|\bпроте\b"


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
    if re.search(r"\b(per month|monthly|month|в месяц|в місяць|месяц|місяць)\b", lowered) or "/month" in lowered:
        return "month"
    if re.search(r"\b(per year|yearly|annual|annually|year|в год|в рік|год|рік)\b", lowered) or "/year" in lowered:
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
    matches = re.findall(
        r"(?<![\w])(\d{1,3}(?:[,\d]{0,3})?(?:\.\d+)?k?)(?![\w])",
        normalized,
        flags=re.IGNORECASE,
    )
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
    return parse_work_formats(text)


def _normalize_english_shorthand_token(value: str | None) -> str | None:
    normalized = _normalize_text(value).lower().replace(" ", "")
    if not normalized:
        return None
    match = re.fullmatch(r"([abcабс])([12])", normalized)
    if match is None:
        return None
    letter = {
        "a": "a",
        "а": "a",
        "b": "b",
        "б": "b",
        "c": "c",
        "с": "c",
    }.get(match.group(1))
    if letter is None:
        return None
    return f"{letter}{match.group(2)}"


def parse_english_level(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    explicit_match = re.search(
        r"\b(?:english|eng|английский|англійська|англійський|англ)\s*(?:level|рівень|уровень)?\s*[:\-]?\s*([abcабс]\s*[12]|native)\b",
        lowered,
    )
    candidate = _normalize_english_shorthand_token(explicit_match.group(1)) if explicit_match is not None else None
    if candidate is None and explicit_match is not None:
        candidate = explicit_match.group(1)
    if candidate is None:
        candidate = _normalize_english_shorthand_token(lowered)
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
            "conversational english",
            "basic english",
            "свободный",
            "вільний",
            "разговорный",
            "розмовний",
            "базовый",
            "базовий",
            "выше среднего",
            "вище середнього",
        ):
            if token in lowered:
                candidate = token
                break
    english_level = normalize_english_level(candidate)
    return {"english_level": english_level} if english_level else {}


def _extract_labeled_value(text: str, label: str) -> Optional[str]:
    pattern = rf"{label}\s*:\s*([^.;\n]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return _normalize_text(match.group(1))


def extract_country_codes(text: str | None) -> list[str]:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return []
    matches: list[tuple[int, int, str]] = []
    for country_name, code in sorted(COUNTRY_CODES.items(), key=lambda item: len(item[0]), reverse=True):
        match = re.search(rf"(?<!\w){re.escape(country_name)}(?!\w)", lowered)
        if match is not None:
            matches.append((match.start(), -len(country_name), code))
    found: list[str] = []
    for _, _, code in sorted(matches):
        if code not in found:
            found.append(code)
    return found


def parse_location(text: str) -> dict:
    normalized = _normalize_text(text)
    location_text = (
        _extract_labeled_value(normalized, "location")
        or _extract_labeled_value(normalized, "локация")
        or _extract_labeled_value(normalized, "локація")
        or _extract_labeled_value(normalized, "based in")
        or _extract_labeled_value(normalized, "located in")
        or _extract_labeled_value(normalized, "нахожусь в")
        or _extract_labeled_value(normalized, "перебуваю в")
    )
    if location_text is None:
        lowered = normalized.lower()
        for marker in (
            "based in ",
            "located in ",
            "from ",
            "in ",
            "живу в ",
            "живу у ",
            "нахожусь в ",
            "перебуваю в ",
            "базуюсь в ",
            "базуюсь у ",
            "знаходжусь у ",
            "знаходжусь в ",
        ):
            if marker in lowered:
                start = lowered.index(marker) + len(marker)
                location_text = normalized[start:].strip(" .")
                break
    if location_text is None:
        lowered = normalized.lower()
        if any(country_name in lowered for country_name in COUNTRY_CODES):
            location_text = normalized.strip(" .")

    if not location_text:
        return {}

    location_text = re.split(
        r"\s+(?:and|but|але|но)\s+(?:open|prefer|preferred|remote|hybrid|office|onsite|on-site|удаленно|удалённо|віддалено|гібрид|гибрид|офис|офіс)\b",
        location_text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,")

    parts = [part.strip() for part in location_text.split(",") if part.strip()]
    country_code = None
    codes = extract_country_codes(location_text)
    if codes:
        country_code = codes[0]

    city = None
    if len(parts) >= 2:
        city = parts[0]
    elif parts:
        single_part = parts[0].lower()
        if single_part not in COUNTRY_CODES:
            city = parts[0]

    return {
        "location_text": location_text,
        "city": city,
        "country_code": country_code,
    }


def parse_preferred_domains(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    if re.search(
        r"\b(any|no preference|open to anything|open to any domain|any domain|без разницы|без різниці|будь-який|любой|будь що|что угодно|мне все равно|мне всё равно|не важно|неважно)\b",
        lowered,
    ):
        return {"preferred_domains_json": ["any"]}
    domains = extract_domains(lowered)
    return {"preferred_domains_json": domains} if domains else {}


def _parse_keyword_boolean(text: str, *, keywords: tuple[str, ...]) -> Optional[bool]:
    lowered = _normalize_text(text).lower()
    if any(keyword in lowered for keyword in keywords):
        if re.search(rf"\b{_NEGATIVE_WORDS}\b", lowered):
            return False
        if re.search(rf"\b{_POSITIVE_WORDS}\b", lowered):
            return True
        return True
    return None


def _extract_local_boolean(text: str, *, keywords: tuple[str, ...]) -> Optional[bool]:
    lowered = _normalize_text(text).lower()
    keyword_patterns = tuple(re.escape(keyword) for keyword in keywords)
    clauses = [
        clause.strip()
        for clause in re.split(_CLAUSE_SPLIT_RE, lowered)
        if clause.strip()
    ]
    relevant_clauses = [clause for clause in clauses if any(keyword in clause for keyword in keywords)]
    for clause in relevant_clauses:
        if re.search(rf"\b{_NEGATIVE_WORDS}\b", clause):
            return False
        if re.search(rf"\b{_POSITIVE_WORDS}\b", clause):
            return True

    positive_patterns = (
        rf"\b{_POSITIVE_WORDS}\b[^.!?\n]{{0,48}}\b(?:{'|'.join(keyword_patterns)})\b",
        rf"\b(?:{'|'.join(keyword_patterns)})\b[^.!?\n]{{0,48}}\b{_POSITIVE_WORDS}\b",
    )
    for pattern in positive_patterns:
        if re.search(pattern, lowered):
            return True

    negative_patterns = (
        rf"\b{_NEGATIVE_WORDS}\b[^.!?\n]{{0,48}}\b(?:{'|'.join(keyword_patterns)})\b",
        rf"\b(?:{'|'.join(keyword_patterns)})\b[^.!?\n]{{0,48}}\b{_NEGATIVE_WORDS}\b",
    )
    for pattern in negative_patterns:
        if re.search(pattern, lowered):
            return False

    if any(token in lowered for token in ("both", "оба", "оба", "обидва")) and any(keyword in lowered for keyword in keywords):
        return True
    if any(token in lowered for token in ("neither", "ни один", "жоден")) and any(keyword in lowered for keyword in keywords):
        return False
    return _parse_keyword_boolean(lowered, keywords=keywords)


def parse_assessment_preferences(text: str) -> dict:
    lowered = _normalize_text(text).lower()
    if re.search(r"\b(no assessments|without assessments|no tests|без тестов|без тестів|без тестовых|без оцінювань)\b", lowered):
        return {
            "show_take_home_task_roles": False,
            "show_live_coding_roles": False,
        }

    payload = {}
    take_home = _extract_local_boolean(
        lowered,
        keywords=(
            "test task",
            "take home",
            "take-home",
            "home assignment",
            "тестовое задание",
            "тестове завдання",
            "домашнее задание",
            "домашнє завдання",
            "тестовая задача",
            "тестова задача",
            "тестовая таска",
            "тестова таска",
            "тестовое",
            "тестове",
            "таска",
            "домашка",
        ),
    )
    live_coding = _extract_local_boolean(
        lowered,
        keywords=("live coding", "live-coding", "pair programming", "coding interview", "лайвкодинг", "лайв кодинг", "парное программирование", "парне програмування"),
    )
    if take_home is not None:
        payload["show_take_home_task_roles"] = take_home
    if live_coding is not None:
        payload["show_live_coding_roles"] = live_coding
    return payload


def parse_candidate_questions(text: str) -> dict:
    normalized = _normalize_text(text)
    parsed = {}
    parsed.update(parse_salary_expectations(normalized))
    parsed.update(parse_work_format(normalized))
    parsed.update(parse_location(normalized))
    parsed.update(parse_english_level(normalized))
    parsed.update(parse_preferred_domains(normalized))
    parsed.update(parse_assessment_preferences(normalized))
    return parsed
