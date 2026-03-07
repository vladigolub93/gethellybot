"""Text normalization helpers shared across user command handlers."""

import re
from typing import Optional


_TRAILING_PUNCTUATION_RE = re.compile(r"[.!?]+$")


def normalize_command_text(text: Optional[str]) -> str:
    """Normalize short user commands for routing and action matching."""
    normalized = (text or "").strip().lower()
    normalized = _TRAILING_PUNCTUATION_RE.sub("", normalized)
    normalized = " ".join(normalized.split())
    return normalized
