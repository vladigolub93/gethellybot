from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


ADMIN_SESSION_COOKIE_NAME = "helly_admin_session"


class AdminSessionError(ValueError):
    """Raised when admin session token cannot be issued or verified."""


@dataclass(frozen=True)
class AdminSessionContext:
    role: str
    issued_at: int
    expires_at: int

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
        }


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def issue_admin_session_token(
    *,
    session_context: AdminSessionContext,
    secret: str,
) -> str:
    if not secret:
        raise AdminSessionError("Admin session secret is not configured.")

    payload_bytes = json.dumps(
        asdict(session_context),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).digest()
    return "{payload}.{signature}".format(
        payload=_urlsafe_b64encode(payload_bytes),
        signature=_urlsafe_b64encode(signature),
    )


def verify_admin_session_token(
    *,
    token: str,
    secret: str,
    now_ts: Optional[int] = None,
) -> AdminSessionContext:
    if not token:
        raise AdminSessionError("Admin session token is required.")
    if not secret:
        raise AdminSessionError("Admin session secret is not configured.")

    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise AdminSessionError("Admin session token format is invalid.") from exc

    payload_bytes = _urlsafe_b64decode(payload_part)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).digest()
    received_signature = _urlsafe_b64decode(signature_part)
    if not hmac.compare_digest(expected_signature, received_signature):
        raise AdminSessionError("Admin session token signature is invalid.")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise AdminSessionError("Admin session payload is invalid.") from exc

    now_ts = int(now_ts or time.time())
    expires_at = int(payload.get("expires_at") or 0)
    if expires_at <= 0 or expires_at < now_ts:
        raise AdminSessionError("Admin session token has expired.")

    role = str(payload.get("role") or "")
    if role != "admin":
        raise AdminSessionError("Admin session role is invalid.")

    return AdminSessionContext(
        role=role,
        issued_at=int(payload["issued_at"]),
        expires_at=expires_at,
    )
