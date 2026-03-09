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


def phrase_matches_verification(*, expected_phrase: str, spoken_text: str) -> bool:
    expected = normalize_verification_text(expected_phrase)
    spoken = normalize_verification_text(spoken_text)
    if not expected or not spoken:
        return False
    if expected in spoken:
        return True

    expected_tokens = expected.split()
    spoken_tokens = spoken.split()
    if expected_tokens:
        position = 0
        for token in spoken_tokens:
            if position < len(expected_tokens) and token == expected_tokens[position]:
                position += 1
        if position == len(expected_tokens):
            return True

    return SequenceMatcher(None, expected, spoken).ratio() >= 0.82
