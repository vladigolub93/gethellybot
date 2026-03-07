from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=64)
def load_system_prompt(*parts: str) -> str:
    path = PROMPTS_ROOT.joinpath(*parts, "SYSTEM.md")
    return path.read_text(encoding="utf-8").strip()
