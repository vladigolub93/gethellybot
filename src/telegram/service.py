from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from src.candidate_profile.service import CandidateProfileService
from src.db.repositories.consents import UserConsentsRepository
from src.db.repositories.files import FilesRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.users import UsersRepository
from src.identity.service import IdentityService
from src.interview.service import InterviewService
from src.telegram.types import NormalizedTelegramUpdate
from src.vacancy.service import VacancyService


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
        self.files_repo = FilesRepository(session)
        self.notifications_repo = NotificationsRepository(session)
        self.identity_service = IdentityService(self.users_repo, self.consents_repo)
        self.candidate_service = CandidateProfileService(session)
        self.interview_service = InterviewService(session)
        self.vacancy_service = VacancyService(session)

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
        persisted_file = self._persist_file_if_present(user.id, raw_message, normalized_update)

        notification_templates = self._apply_identity_flow(
            user,
            raw_message.id,
            normalized_update,
            file_id=persisted_file.id if persisted_file is not None else None,
        )
        self.session.commit()

        return ProcessedTelegramUpdate(
            status="processed",
            deduplicated=False,
            notification_templates=notification_templates,
            user_id=str(user.id),
        )

    def _apply_identity_flow(
        self,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        *,
        file_id=None,
    ) -> List[str]:
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
            if role == "candidate":
                self.candidate_service.start_onboarding(
                    user, trigger_ref_id=raw_message_id
                )
            else:
                self.vacancy_service.start_onboarding(
                    user, trigger_ref_id=raw_message_id
                )
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

        if user.is_candidate and normalized_update.content_type in {"text", "voice", "video"}:
            interview_result = self.interview_service.handle_candidate_message(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                text=normalized_update.text,
                file_id=file_id,
            )
            if interview_result is not None:
                templates.append(
                    self._notify(
                        user.id,
                        interview_result.notification_template,
                        {"text": interview_result.notification_text},
                    )
                )
                return templates

        if user.is_candidate and normalized_update.content_type == "text":
            summary_review_result = self.candidate_service.handle_summary_review_action(
                user=user,
                raw_message_id=raw_message_id,
                text=normalized_update.text,
            )
            if summary_review_result is not None:
                message_map = {
                    "candidate_summary_approved": "Summary approved. Send your salary expectations, current location, and preferred work format (remote, hybrid, or office).",
                    "candidate_summary_edit_processing": "Summary edits received. Updating your profile summary.",
                    "candidate_summary_edit_limit_reached": "Summary edit limit reached. Please approve the latest summary or restart profile creation.",
                    "candidate_summary_edit_empty": "Please send summary edits after 'Edit summary:'.",
                    "candidate_summary_not_available": "No current summary is available to review.",
                    "candidate_summary_review_help": "Reply 'Approve summary' or 'Edit summary: ...' while reviewing your summary.",
                }
                templates.append(
                    self._notify(
                        user.id,
                        summary_review_result.notification_template,
                        {"text": message_map[summary_review_result.notification_template]},
                    )
                )
                return templates

        if user.is_candidate and normalized_update.content_type in {"text", "video"}:
            verification_result = self.candidate_service.handle_verification_submission(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                file_id=file_id,
            )
            if verification_result is not None:
                templates.append(
                    self._notify(
                        user.id,
                        verification_result.notification_template,
                        {"text": verification_result.notification_text},
                    )
                )
                return templates

        if user.is_candidate and normalized_update.content_type in {"text", "voice", "video"}:
            questions_result = self.candidate_service.handle_questions_answer(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                text=normalized_update.text,
                file_id=file_id,
            )
            if questions_result is not None:
                templates.append(
                    self._notify(
                        user.id,
                        questions_result.notification_template,
                        {"text": questions_result.notification_text},
                    )
                )
                return templates

        if user.is_hiring_manager and normalized_update.content_type in {"text", "voice", "video"}:
            clarification_result = self.vacancy_service.handle_clarification_answer(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                text=normalized_update.text,
                file_id=file_id,
            )
            if clarification_result is not None:
                templates.append(
                    self._notify(
                        user.id,
                        clarification_result.notification_template,
                        {"text": clarification_result.notification_text},
                    )
                )
                return templates

        if user.is_hiring_manager and normalized_update.content_type in {"text", "document", "voice", "video"}:
            intake_result = self.vacancy_service.handle_jd_intake(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                text=normalized_update.text,
                file_id=file_id,
            )
            message_map = {
                "vacancy_jd_received_processing": "Job description received. Processing started.",
                "manager_input_not_expected": "Manager input is not expected at the current step.",
                "manager_input_unsupported": "Please send the job description as text, document, voice, or video.",
            }
            templates.append(
                self._notify(
                    user.id,
                    intake_result.notification_template,
                    {"text": message_map[intake_result.notification_template]},
                )
            )
            return templates

        if user.is_candidate and normalized_update.content_type in {"text", "document", "voice"}:
            intake_result = self.candidate_service.handle_cv_intake(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                text=normalized_update.text,
                file_id=file_id,
            )
            message_map = {
                "candidate_cv_received_processing": "CV or experience input received. Processing started.",
                "candidate_input_not_expected": "Candidate input is not expected at the current step.",
                "candidate_input_unsupported": "Please send text, a document, or a voice message for your experience.",
            }
            templates.append(
                self._notify(
                    user.id,
                    intake_result.notification_template,
                    {"text": message_map[intake_result.notification_template]},
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

    def _persist_file_if_present(self, user_id, raw_message, normalized_update: NormalizedTelegramUpdate):
        if normalized_update.file is None:
            return None

        file_row = self.files_repo.create_or_get_from_telegram(
            owner_user_id=user_id,
            kind=normalized_update.file.kind,
            telegram_file_id=normalized_update.file.telegram_file_id,
            telegram_unique_file_id=normalized_update.file.telegram_unique_file_id,
            mime_type=normalized_update.file.mime_type,
            extension=normalized_update.file.extension,
            size_bytes=normalized_update.file.size_bytes,
            provider_metadata=normalized_update.file.payload,
        )
        self.raw_messages_repo.attach_file(raw_message, file_row.id)
        return file_row

    def _notify(self, user_id, template_key: str, payload: dict) -> str:
        self.notifications_repo.create(
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            template_key=template_key,
            payload_json=payload,
        )
        return template_key
