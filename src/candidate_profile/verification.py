from __future__ import annotations

import re
import secrets
from difflib import SequenceMatcher

VERIFICATION_PHRASES = (
    "green deploy",
    "clean merge",
    "fast commit",
    "dark mode",
    "cache hit",
    "safe rollback",
    "zero downtime",
    "hotfix ready",
    "backend online",
    "frontend shipped",
    "cloud sync",
    "stable build",
    "async queue",
    "solid release",
    "smart webhook",
    "quick deploy",
    "clean branch",
    "prod is green",
    "tiny hotfix",
    "sync complete",
)


def build_verification_phrase(*, profile_id, attempt_no: int) -> str:
    del profile_id, attempt_no
    return f"Helly check: {secrets.choice(VERIFICATION_PHRASES)}"


def normalize_verification_text(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _token_matches(expected_token: str, spoken_token: str) -> bool:
    if expected_token == spoken_token:
        return True
    return SequenceMatcher(None, expected_token, spoken_token).ratio() >= 0.74


def _ordered_token_match(expected_tokens: list[str], spoken_tokens: list[str]) -> bool:
    if not expected_tokens or not spoken_tokens:
        return False

    position = 0
    for spoken_token in spoken_tokens:
        if position < len(expected_tokens) and _token_matches(expected_tokens[position], spoken_token):
            position += 1
    return position == len(expected_tokens)


def _token_coverage_ratio(expected_tokens: list[str], spoken_tokens: list[str]) -> float:
    if not expected_tokens or not spoken_tokens:
        return 0.0

    matched = 0
    remaining = list(spoken_tokens)
    for expected_token in expected_tokens:
        for index, spoken_token in enumerate(remaining):
            if _token_matches(expected_token, spoken_token):
                matched += 1
                remaining.pop(index)
                break
    return matched / len(expected_tokens)


def phrase_matches_verification(*, expected_phrase: str, spoken_text: str) -> bool:
    expected = normalize_verification_text(expected_phrase)
    spoken = normalize_verification_text(spoken_text)
    if not expected or not spoken:
        return False
    if expected in spoken:
        return True

    expected_body = expected
    if expected.startswith("helly check "):
        expected_body = expected[len("helly check ") :].strip()

    if expected_body and expected_body in spoken:
        return True

    expected_tokens = expected.split()
    spoken_tokens = spoken.split()
    if _ordered_token_match(expected_tokens, spoken_tokens):
        return True

    expected_body_tokens = expected_body.split()
    if _ordered_token_match(expected_body_tokens, spoken_tokens):
        return True

    if expected_body_tokens:
        body_coverage = _token_coverage_ratio(expected_body_tokens, spoken_tokens)
        if len(expected_body_tokens) >= 3 and body_coverage >= 0.67:
            return True
        if len(expected_body_tokens) == 2 and body_coverage >= 1.0:
            return True

    if expected_body and SequenceMatcher(None, expected_body, spoken).ratio() >= 0.82:
        return True

    return SequenceMatcher(None, expected, spoken).ratio() >= 0.82


def format_verification_transcript_hint(spoken_text: str) -> str:
    normalized = " ".join((spoken_text or "").split()).strip()
    if not normalized:
        return "What I heard: [empty transcript]"
    return f'What I heard: "{normalized}"'


def format_verification_phrase_feedback(*, expected_phrase: str, spoken_text: str) -> str:
    normalized_spoken = " ".join((spoken_text or "").split()).strip()
    normalized_expected = " ".join((expected_phrase or "").split()).strip()
    heard_text = f'"{normalized_spoken}"' if normalized_spoken else "[empty transcript]"
    return f'I heard on the video: {heard_text}. You were supposed to say: "{normalized_expected}".'
