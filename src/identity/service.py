from __future__ import annotations

from src.db.repositories.consents import UserConsentsRepository
from src.db.repositories.users import UsersRepository


class IdentityService:
    def __init__(self, users_repo: UsersRepository, consents_repo: UserConsentsRepository | None):
        self.users_repo = users_repo
        self.consents_repo = consents_repo

    def ensure_user(self, normalized_update):
        return self.users_repo.create_or_update_from_telegram(
            telegram_user_id=normalized_update.telegram_user_id,
            telegram_chat_id=normalized_update.telegram_chat_id,
            display_name=normalized_update.display_name,
            username=normalized_update.username,
            language_code=normalized_update.language_code,
            chat_type=normalized_update.chat_type,
        )

    def attach_contact(self, user, normalized_update):
        return self.users_repo.attach_contact(user, normalized_update.contact_phone_number)

    def has_data_processing_consent(self, user) -> bool:
        if self.consents_repo is None:
            return True
        return self.consents_repo.has_granted(user.id, "data_processing")

    def grant_data_processing_consent(self, user, source_raw_message_id=None):
        if self.consents_repo is None:
            return None
        return self.consents_repo.grant(
            user_id=user.id,
            consent_type="data_processing",
            source_raw_message_id=source_raw_message_id,
        )

    def set_role(self, user, role: str):
        return self.users_repo.set_role(user, role)
