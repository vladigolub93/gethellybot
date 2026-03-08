from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"
DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"


@lru_cache(maxsize=1)
def load_shared_telegram_style_rules() -> str:
    path = PROMPTS_ROOT / "_shared" / "TELEGRAM_STYLE.md"
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=64)
def load_system_prompt(*parts: str) -> str:
    path = PROMPTS_ROOT.joinpath(*parts, "SYSTEM.md")
    base_prompt = path.read_text(encoding="utf-8").strip()
    shared_style = load_shared_telegram_style_rules()
    return "\n\n".join(
        [
            base_prompt,
            "Shared Telegram Delivery Rules:",
            shared_style,
        ]
    ).strip()


@lru_cache(maxsize=1)
def load_agent_knowledge_base() -> str:
    path = DOCS_ROOT / "HELLY_V1_AGENT_KNOWLEDGE_BASE.md"
    return path.read_text(encoding="utf-8").strip()


def build_user_facing_grounded_system_prompt(*parts: str) -> str:
    base_prompt = load_system_prompt(*parts)
    knowledge_base = load_agent_knowledge_base()
    return "\n\n".join(
        [
            base_prompt,
            "Shared Helly Product Knowledge Base:",
            knowledge_base,
            (
                "Use the knowledge base above as product-truth grounding for any user-facing explanation. "
                "Do not contradict it, and do not invent product behavior beyond it."
            ),
        ]
    ).strip()
