import time

import pytest

from src.webapp.session import (
    WebAppSessionContext,
    WebAppSessionError,
    issue_webapp_session_token,
    verify_webapp_session_token,
)


def test_issue_and_verify_webapp_session_token_roundtrip() -> None:
    session_context = WebAppSessionContext(
        telegram_user_id=123456,
        role="candidate",
        user_id="user-1",
        display_name="Vlad Golub",
        issued_at=int(time.time()),
        expires_at=int(time.time()) + 3600,
    )

    token = issue_webapp_session_token(
        session_context=session_context,
        secret="secret-value",
    )
    verified = verify_webapp_session_token(
        token=token,
        secret="secret-value",
    )

    assert verified.telegram_user_id == 123456
    assert verified.role == "candidate"
    assert verified.user_id == "user-1"


def test_verify_webapp_session_token_rejects_bad_signature() -> None:
    session_context = WebAppSessionContext(
        telegram_user_id=123456,
        role="candidate",
        user_id="user-1",
        display_name="Vlad Golub",
        issued_at=int(time.time()),
        expires_at=int(time.time()) + 3600,
    )
    token = issue_webapp_session_token(
        session_context=session_context,
        secret="secret-value",
    )

    with pytest.raises(WebAppSessionError, match="signature is invalid"):
        verify_webapp_session_token(
            token=token,
            secret="different-secret",
        )


def test_verify_webapp_session_token_rejects_expired_token() -> None:
    session_context = WebAppSessionContext(
        telegram_user_id=123456,
        role="candidate",
        user_id="user-1",
        display_name="Vlad Golub",
        issued_at=int(time.time()) - 20,
        expires_at=int(time.time()) - 10,
    )
    token = issue_webapp_session_token(
        session_context=session_context,
        secret="secret-value",
    )

    with pytest.raises(WebAppSessionError, match="has expired"):
        verify_webapp_session_token(
            token=token,
            secret="secret-value",
        )
