from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from src.db.repositories.consents import UserConsentsRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.users import UsersRepository
from src.identity.service import IdentityService
from src.telegram.types import NormalizedTelegramUpdate


@dataclass(frozen=True)
class ProcessedTelegramUpdate:
    status: str
    deduplicated: bool
    notification_templates: List[str]
    user_id: str


class TelegramUpdateService:
    def __init__(self, session: Session):
        self.session = session
        self.users_repo = UsersRepository(session)
        self.raw_messages_repo = RawMessagesRepository(session)
        self.consents_repo = UserConsentsRepository(session)
        self.notifications_repo = NotificationsRepository(session)
        self.identity_service = IdentityService(self.users_repo, self.consents_repo)

    def process(self, normalized_update: NormalizedTelegramUpdate) -> ProcessedTelegramUpdate:
        existing = self.raw_messages_repo.get_by_update_id(normalized_update.update_id)
        if existing is not None:
            return ProcessedTelegramUpdate(
                status="duplicate",
                deduplicated=True,
                notification_templates=[],
                user_id=str(existing.user_id) if existing.user_id else "",
            )

        user = self.identity_service.ensure_user(normalized_update)
        raw_message = self.raw_messages_repo.create(
            user_id=user.id,
            telegram_update_id=normalized_update.update_id,
            telegram_message_id=normalized_update.message_id,
            telegram_chat_id=normalized_update.telegram_chat_id,
            direction="inbound",
            content_type=normalized_update.content_type,
            payload_json=normalized_update.payload,
            text_content=normalized_update.text,
        )

        notification_templates = self._apply_identity_flow(user, raw_message.id, normalized_update)
        self.session.commit()

        return ProcessedTelegramUpdate(
            status="processed",
            deduplicated=False,
            notification_templates=notification_templates,
            user_id=str(user.id),
        )

    def _apply_identity_flow(self, user, raw_message_id, normalized_update: NormalizedTelegramUpdate) -> List[str]:
        templates: List[str] = []
        text_value = (normalized_update.text or "").strip().lower()

        if normalized_update.contact_phone_number:
            self.identity_service.attach_contact(user, normalized_update)
            if not self.identity_service.has_data_processing_consent(user):
                templates.append(
                    self._notify(
                        user.id,
                        "request_consent",
                        {
                            "text": "Please confirm data processing consent by replying 'I agree'.",
                        },
                    )
                )
            else:
                templates.append(self._notify(user.id, "request_role", {"text": "Choose your role: Candidate or Hiring Manager."}))
            return templates

        if text_value == "/start":
            if not user.phone_number:
                templates.append(
                    self._notify(
                        user.id,
                        "request_contact",
                        {"text": "Please share your contact to continue."},
                    )
                )
                return templates

            if not self.identity_service.has_data_processing_consent(user):
                templates.append(
                    self._notify(
                        user.id,
                        "request_consent",
                        {"text": "Please confirm data processing consent by replying 'I agree'."},
                    )
                )
                return templates

            templates.append(
                self._notify(
                    user.id,
                    "request_role",
                    {"text": "Choose your role: Candidate or Hiring Manager."},
                )
            )
            return templates

        if text_value in {"i agree", "agree", "consent"}:
            self.identity_service.grant_data_processing_consent(
                user, source_raw_message_id=raw_message_id
            )
            templates.append(
                self._notify(
                    user.id,
                    "request_role",
                    {"text": "Consent recorded. Choose your role: Candidate or Hiring Manager."},
                )
            )
            return templates

        if text_value in {"candidate", "hiring manager"}:
            if not user.phone_number:
                templates.append(
                    self._notify(
                        user.id,
                        "request_contact",
                        {"text": "Please share your contact before choosing a role."},
                    )
                )
                return templates

            if not self.identity_service.has_data_processing_consent(user):
                templates.append(
                    self._notify(
                        user.id,
                        "request_consent",
                        {"text": "Please confirm consent before choosing a role."},
                    )
                )
                return templates

            role = "candidate" if text_value == "candidate" else "hiring_manager"
            self.identity_service.set_role(user, role)
            template_key = (
                "candidate_onboarding_started"
                if role == "candidate"
                else "manager_onboarding_started"
            )
            message_text = (
                "Candidate flow started. Please upload your CV or describe your experience."
                if role == "candidate"
                else "Hiring manager flow started. Please send the job description."
            )
            templates.append(
                self._notify(
                    user.id,
                    template_key,
                    {"text": message_text},
                )
            )
            return templates

        templates.append(
            self._notify(
                user.id,
                "unsupported_input",
                {"text": "Unsupported input for the current baseline. Use /start to begin."},
            )
        )
        return templates

    def _notify(self, user_id, template_key: str, payload: dict) -> str:
        self.notifications_repo.create(
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            template_key=template_key,
            payload_json=payload,
        )
        return template_key

