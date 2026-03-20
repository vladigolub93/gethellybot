from __future__ import annotations

import time

from src.admin.session import AdminSessionContext, issue_admin_session_token
from src.config.settings import get_settings


def issue_admin_session_for_pin(*, provided_pin: str) -> tuple[str, AdminSessionContext]:
    settings = get_settings()
    expected_pin = settings.effective_admin_panel_pin
    if not expected_pin or str(provided_pin or "").strip() != str(expected_pin).strip():
        raise ValueError("Invalid admin PIN.")

    now_ts = int(time.time())
    session_context = AdminSessionContext(
        role="admin",
        issued_at=now_ts,
        expires_at=now_ts + settings.admin_session_ttl_seconds,
    )
    token = issue_admin_session_token(
        session_context=session_context,
        secret=settings.effective_admin_session_secret,
    )
    return token, session_context
