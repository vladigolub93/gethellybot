from __future__ import annotations

from src.orchestrator.policy import ResolvedStateContext


def state_assistance_prompt(
    *,
    context: ResolvedStateContext,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: respond to the user's latest message inside the current Helly workflow state.

Current role: {context.role}
Current state: {context.state}
State goal: {context.goal}
Allowed actions: {context.allowed_actions}
Blocked actions: {context.blocked_actions}
Missing requirements: {context.missing_requirements}
Current step guidance: {context.guidance_text}
Fallback help text: {context.help_text or ""}
Recent context: {recent_context or []}

Latest user message:
{latest_user_message}
"""
