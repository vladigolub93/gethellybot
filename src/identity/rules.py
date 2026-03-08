from __future__ import annotations


def has_primary_contact_channel(user) -> bool:
    return bool(getattr(user, "phone_number", None) or getattr(user, "username", None))
