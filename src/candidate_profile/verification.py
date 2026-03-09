from __future__ import annotations

import secrets

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
