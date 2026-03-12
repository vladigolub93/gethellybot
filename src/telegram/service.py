from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

from sqlalchemy.orm import Session

from src.candidate_profile.service import CandidateProfileService
from src.config.logging import get_logger
from src.db.repositories.files import FilesRepository
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.users import UsersRepository
from src.evaluation.service import EvaluationService
from src.graph.service import LangGraphStageAgentService
from src.identity.rules import has_primary_contact_channel
from src.identity.service import IdentityService
from src.interview.service import InterviewService
from src.integrations.telegram_bot import TelegramBotClient
from src.matching.review import MatchingReviewService
from src.messaging.service import MessagingService
from src.notifications.delivery import NotificationDeliveryService
from src.orchestrator.policy import resolve_state_context
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.processor import process_job
from src.jobs.queue import JobMessage
from src.monitoring.telegram_alerts import TelegramErrorAlertService
from src.shared.text import normalize_command_text
from src.telegram.keyboards import (
    contact_request_keyboard,
    deletion_confirmation_keyboard,
    remove_keyboard,
    role_selection_keyboard,
    summary_review_keyboard,
)
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
        self.logger = get_logger(__name__)
        self.session = session
        self.users_repo = UsersRepository(session)
        self.raw_messages_repo = RawMessagesRepository(session)
        self.files_repo = FilesRepository(session)
        self.notifications_repo = NotificationsRepository(session)
        self.identity_service = IdentityService(self.users_repo, None)
        self.messaging = MessagingService(session)
        self.stage_agents = LangGraphStageAgentService(session)
        self.candidate_service = CandidateProfileService(session)
        self.evaluation_service = EvaluationService(session)
        self.interview_service = InterviewService(session)
        self.matching_review_service = MatchingReviewService(session)
        self.vacancy_service = VacancyService(session)
        self.notification_delivery = NotificationDeliveryService(session)
        self._safe_immediate_job_types = {
            "file_store_telegram_v1",
            "candidate_cv_extract_v1",
            "candidate_summary_edit_apply_v1",
            "candidate_questions_parse_v1",
            "vacancy_jd_extract_v1",
            "vacancy_summary_edit_apply_v1",
        }

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    def _candidate_cv_intake_message(self, *, notification_template: str, content_type: str) -> str:
        if notification_template == "candidate_cv_received_processing":
            if content_type == "document":
                return self._copy("Nice, got your CV file. I’m turning it into a short summary now.")
            if content_type == "voice":
                return self._copy("Nice, got your voice description. I’m turning it into a short summary now.")
            return self._copy("Nice, got your experience text. I’m turning it into a short summary now.")
        if notification_template == "candidate_cv_needs_more_detail":
            return self._copy(
                "Send the actual CV text or a short work summary with a bit more detail, or just upload the CV file instead."
            )
        if notification_template == "candidate_input_not_expected":
            return self._copy("Candidate input is not expected at the current step.")
        return self._copy("Send your experience as text, a file, or a voice note.")

    def _entry_stage_reply_markup(self, stage: str | None):
        if stage == "CONTACT_REQUIRED":
            return contact_request_keyboard()
        if stage == "ROLE_SELECTION":
            return role_selection_keyboard()
        return None

    def _notify_entry_stage(
        self,
        *,
        user_id,
        stage: str,
        text: str,
    ) -> str:
        template_key = {
            "CONTACT_REQUIRED": "request_contact",
            "ROLE_SELECTION": "request_role",
        }.get(stage, "state_aware_help")
        return self._notify(
            user_id,
            template_key,
            {
                "text": text,
                "reply_markup": self._entry_stage_reply_markup(stage),
            },
        )

    def _handle_contact_share(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
    ) -> List[str]:
        self.identity_service.attach_contact(user, normalized_update)
        return [
            self._notify_entry_stage(
                user_id=user.id,
                stage="ROLE_SELECTION",
                text=self.messaging.compose_role_selection(),
            )
        ]

    def _handle_start_command(self, *, user) -> List[str]:
        if not has_primary_contact_channel(user):
            return [
                self._notify_entry_stage(
                    user_id=user.id,
                    stage="CONTACT_REQUIRED",
                    text=self._copy(
                        "Share your contact with the button below and I’ll keep things moving."
                    ),
                )
            ]
        return [
            self._notify_entry_stage(
                user_id=user.id,
                stage="ROLE_SELECTION",
                text=self.messaging.compose_role_selection(),
            )
        ]

    def _handle_entry_stage_result(
        self,
        *,
        user,
        raw_message_id,
        entry_result,
    ) -> List[str] | None:
        if entry_result is None:
            return None

        if entry_result.action_accepted and entry_result.proposed_action in {"candidate", "hiring_manager"}:
            role = "candidate" if entry_result.proposed_action == "candidate" else "hiring_manager"
            self.identity_service.set_role(user, role)
            if role == "candidate":
                self.candidate_service.start_onboarding(user, trigger_ref_id=raw_message_id)
            else:
                self.vacancy_service.start_onboarding(user, trigger_ref_id=raw_message_id)
            template_key = (
                "candidate_onboarding_started"
                if role == "candidate"
                else "manager_onboarding_started"
            )
            message_text = (
                "Nice. Send me your CV, or just describe your experience here."
                if role == "candidate"
                else "Nice. Send me the job description and I’ll turn it into a clean vacancy draft."
            )
            return [
                self._notify(
                    user.id,
                    template_key,
                    {
                        "text": self._copy(message_text),
                        "reply_markup": remove_keyboard(),
                    },
                )
            ]

        if entry_result.reply_text:
            return [
                self._notify_entry_stage(
                    user_id=user.id,
                    stage=entry_result.stage,
                    text=entry_result.reply_text,
                )
            ]

        return None

    def _resolve_graph_help_text(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
        stage_result=None,
    ) -> str | None:
        if stage_result is not None:
            if not stage_result.action_accepted and stage_result.reply_text:
                return stage_result.reply_text
            return None
        graph_reply = self.stage_agents.maybe_build_stage_reply(
            user=user,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        return graph_reply

    def _maybe_run_graph_stage(
        self,
        *,
        user,
        normalized_update: NormalizedTelegramUpdate,
    ):
        if normalized_update.content_type == "text" and not (normalized_update.text or "").strip():
            return None
        return self.stage_agents.maybe_run_stage(
            user=user,
            latest_user_message=normalized_update.text or "",
            latest_message_type=normalized_update.content_type,
        )

    def _notify_result(
        self,
        *,
        user_id,
        template_key: str,
        text: str,
        reply_markup=None,
        allow_duplicate: bool = False,
    ) -> str:
        return self._notify(
            user_id,
            template_key,
            {
                "text": text,
                "reply_markup": reply_markup,
            },
            allow_duplicate=allow_duplicate,
        )

    def _dispatch_segment_chain(
        self,
        *,
        content_type: str,
        segments: Sequence[tuple[set[str], Callable[[], List[str] | None]]],
    ) -> List[str] | None:
        for allowed_content_types, handler in segments:
            if content_type not in allowed_content_types:
                continue
            templates = handler()
            if templates is not None:
                return templates
        return None

    def _maybe_handle_graph_help(
        self,
        *,
        user,
        latest_user_message: str,
        user_id,
        stage_result=None,
        reply_markup=None,
    ) -> List[str] | None:
        assistance_text = self._resolve_graph_help_text(
            user=user,
            latest_user_message=latest_user_message,
            stage_result=stage_result,
        )
        if not assistance_text:
            return None
        return [
            self._notify_result(
                user_id=user_id,
                template_key="state_aware_help",
                text=assistance_text,
                reply_markup=reply_markup,
            )
        ]

    def _handle_candidate_delete_stage_action(
        self,
        *,
        user,
        raw_message_id,
        stage_result,
    ) -> List[str] | None:
        if stage_result is None or stage_result.stage not in {"READY", "DELETE_CONFIRMATION"}:
            return None
        if stage_result.stage == "READY":
            if not (
                stage_result.action_accepted
                and stage_result.proposed_action in {"delete_profile", "find_matching_vacancies", "update_matching_preferences"}
            ):
                return None
            if stage_result.proposed_action in {"find_matching_vacancies", "update_matching_preferences"}:
                ready_result = self.candidate_service.execute_ready_action(
                    user=user,
                    raw_message_id=raw_message_id,
                    action=stage_result.proposed_action,
                    structured_payload=stage_result.structured_payload or {},
                )
                if ready_result is None:
                    return None
                return [
                    self._notify_result(
                        user_id=user.id,
                        template_key=ready_result.notification_template,
                        text=ready_result.notification_text,
                        reply_markup=getattr(ready_result, "reply_markup", None),
                        allow_duplicate=True,
                    )
                ]
            deletion_text = "delete profile"
        else:
            if not (
                stage_result.action_accepted
                and stage_result.proposed_action in {"confirm_delete", "cancel_delete"}
            ):
                return None
            deletion_text = (
                "Confirm delete profile"
                if stage_result.proposed_action == "confirm_delete"
                else "Cancel delete"
            )
        deletion_result = self.candidate_service.execute_deletion_action(
            user=user,
            raw_message_id=raw_message_id,
            action="delete_profile" if stage_result.stage == "READY" else stage_result.proposed_action,
        )
        if deletion_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=deletion_result.notification_template,
                text=deletion_result.notification_text,
                reply_markup=deletion_confirmation_keyboard("candidate")
                if deletion_result.status == "confirmation_required"
                else remove_keyboard(),
            )
        ]

    def _handle_candidate_vacancy_review_stage_action(
        self,
        *,
        user,
        raw_message_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "VACANCY_REVIEW"
            and stage_result.action_accepted
            and stage_result.proposed_action in {"apply_to_vacancy", "skip_vacancy", "update_matching_preferences"}
        ):
            return None
        if stage_result.proposed_action == "update_matching_preferences":
            ready_result = self.candidate_service.execute_ready_action(
                user=user,
                raw_message_id=raw_message_id,
                action="update_matching_preferences",
                structured_payload=stage_result.structured_payload or {},
            )
            if ready_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=ready_result.notification_template,
                    text=ready_result.notification_text,
                    reply_markup=getattr(ready_result, "reply_markup", None),
                    allow_duplicate=True,
                )
            ]
        result = self.matching_review_service.execute_candidate_pre_interview_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
            vacancy_slot=(stage_result.structured_payload or {}).get("vacancy_slot"),
        )
        if result is None:
            return None
        return []

    def _handle_manager_delete_stage_action(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        if stage_result is None or stage_result.stage not in {"OPEN", "DELETE_CONFIRMATION"}:
            return None
        if stage_result.stage == "OPEN":
            if not (
                stage_result.action_accepted
                and stage_result.proposed_action in {"delete_vacancy", "update_vacancy_preferences"}
            ):
                return None
            if stage_result.proposed_action == "update_vacancy_preferences":
                open_result = self.vacancy_service.execute_open_action(
                    user=user,
                    raw_message_id=raw_message_id,
                    action=stage_result.proposed_action,
                    structured_payload=stage_result.structured_payload or {},
                    latest_user_message=latest_user_message,
                )
                if open_result is None:
                    return None
                return [
                    self._notify_result(
                        user_id=user.id,
                        template_key=open_result.notification_template,
                        text=open_result.notification_text,
                    )
                ]
            deletion_text = "delete vacancy"
        else:
            if not (
                stage_result.action_accepted
                and stage_result.proposed_action in {"confirm_delete", "cancel_delete"}
            ):
                return None
            deletion_text = (
                "Confirm delete vacancy"
                if stage_result.proposed_action == "confirm_delete"
                else "Cancel delete"
            )
        deletion_result = self.vacancy_service.execute_deletion_action(
            user=user,
            raw_message_id=raw_message_id,
            action="delete_vacancy" if stage_result.stage == "OPEN" else stage_result.proposed_action,
            latest_user_message=latest_user_message,
        )
        if deletion_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=deletion_result.notification_template,
                text=deletion_result.notification_text,
                reply_markup=deletion_confirmation_keyboard("vacancy")
                if deletion_result.status == "confirmation_required"
                else remove_keyboard(),
            )
        ]

    def _handle_manager_review_stage_action(
        self,
        *,
        user,
        raw_message_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "MANAGER_REVIEW"
            and stage_result.action_accepted
            and stage_result.proposed_action in {"approve_candidate", "reject_candidate"}
        ):
            return None
        manager_result = self.evaluation_service.execute_manager_review_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
        )
        if manager_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=manager_result.notification_template,
                text=manager_result.notification_text,
                reply_markup=remove_keyboard() if manager_result.status != "help" else None,
            )
        ]

    def _handle_manager_pre_interview_stage_action(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str | None,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "PRE_INTERVIEW_REVIEW"
            and stage_result.action_accepted
            and stage_result.proposed_action in {"interview_candidate", "skip_candidate", "update_vacancy_preferences"}
        ):
            return None
        if stage_result.proposed_action == "update_vacancy_preferences":
            open_result = self.vacancy_service.execute_open_action(
                user=user,
                raw_message_id=raw_message_id,
                action=stage_result.proposed_action,
                structured_payload=stage_result.structured_payload or {},
                latest_user_message=latest_user_message,
            )
            if open_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=open_result.notification_template,
                    text=open_result.notification_text,
                )
            ]
        result = self.matching_review_service.execute_manager_pre_interview_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
            candidate_slot=(stage_result.structured_payload or {}).get("candidate_slot"),
        )
        if result is None:
            return None
        return []

    def _handle_callback_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
    ) -> List[str] | None:
        if normalized_update.content_type != "callback":
            return None

        callback_data = (normalized_update.callback_data or "").strip()
        if not callback_data:
            return []

        if callback_data.startswith("mgr_pre:int:"):
            match_id = callback_data[len("mgr_pre:int:") :]
            result = self.matching_review_service.execute_manager_pre_interview_action(
                user=user,
                raw_message_id=raw_message_id,
                action="interview_candidate",
                candidate_slot=None,
                match_id=match_id,
            )
            return [] if result is not None else None

        if callback_data.startswith("mgr_pre:skip:"):
            match_id = callback_data[len("mgr_pre:skip:") :]
            result = self.matching_review_service.execute_manager_pre_interview_action(
                user=user,
                raw_message_id=raw_message_id,
                action="skip_candidate",
                candidate_slot=None,
                match_id=match_id,
            )
            return [] if result is not None else None

        if callback_data.startswith("mgr_rev:approve:"):
            match_id = callback_data[len("mgr_rev:approve:") :]
            manager_result = self.evaluation_service.execute_manager_review_action(
                user=user,
                raw_message_id=raw_message_id,
                action="approve_candidate",
                match_id=match_id,
            )
            if manager_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=manager_result.notification_template,
                    text=manager_result.notification_text,
                    reply_markup=remove_keyboard() if manager_result.status != "help" else None,
                )
            ]

        if callback_data.startswith("mgr_rev:reject:"):
            match_id = callback_data[len("mgr_rev:reject:") :]
            manager_result = self.evaluation_service.execute_manager_review_action(
                user=user,
                raw_message_id=raw_message_id,
                action="reject_candidate",
                match_id=match_id,
            )
            if manager_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=manager_result.notification_template,
                    text=manager_result.notification_text,
                    reply_markup=remove_keyboard() if manager_result.status != "help" else None,
                )
            ]

        if callback_data.startswith("cand_pre:apply:"):
            match_id = callback_data[len("cand_pre:apply:") :]
            result = self.matching_review_service.execute_candidate_pre_interview_action(
                user=user,
                raw_message_id=raw_message_id,
                action="apply_to_vacancy",
                vacancy_slot=None,
                match_id=match_id,
            )
            return [] if result is not None else None

        if callback_data.startswith("cand_pre:skip:"):
            match_id = callback_data[len("cand_pre:skip:") :]
            result = self.matching_review_service.execute_candidate_pre_interview_action(
                user=user,
                raw_message_id=raw_message_id,
                action="skip_vacancy",
                vacancy_slot=None,
                match_id=match_id,
            )
            return [] if result is not None else None

        if callback_data.startswith("cand_inv:accept:"):
            match_id = callback_data[len("cand_inv:accept:") :]
            interview_result = self.interview_service.execute_invitation_action(
                user=user,
                raw_message_id=raw_message_id,
                action="accept_interview",
                match_id=match_id,
            )
            if interview_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=interview_result.notification_template,
                    text=interview_result.notification_text,
                    reply_markup=remove_keyboard()
                    if interview_result.status in {"accepted", "skipped"}
                    else None,
                )
            ]

        if callback_data.startswith("cand_inv:skip:"):
            match_id = callback_data[len("cand_inv:skip:") :]
            interview_result = self.interview_service.execute_invitation_action(
                user=user,
                raw_message_id=raw_message_id,
                action="skip_opportunity",
                match_id=match_id,
            )
            if interview_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=interview_result.notification_template,
                    text=interview_result.notification_text,
                    reply_markup=remove_keyboard()
                    if interview_result.status in {"accepted", "skipped"}
                    else None,
                )
            ]

        return []

    def _handle_manager_open_stage_action(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str | None,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "OPEN"
            and stage_result.action_accepted
            and stage_result.proposed_action in {
                "create_new_vacancy",
                "list_open_vacancies",
                "find_matching_candidates",
            }
        ):
            return None
        open_result = self.vacancy_service.execute_open_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
            latest_user_message=latest_user_message,
        )
        if open_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=open_result.notification_template,
                text=open_result.notification_text,
                reply_markup=remove_keyboard()
                if stage_result.proposed_action == "create_new_vacancy"
                else None,
                allow_duplicate=stage_result.proposed_action == "find_matching_candidates",
            )
        ]

    def _handle_candidate_interaction_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if stage_result is None or not stage_result.action_accepted:
            return None
        if stage_result.stage == "INTERVIEW_INVITED" and stage_result.proposed_action in {
            "accept_interview",
            "skip_opportunity",
        }:
            if hasattr(self.interview_service, "execute_invitation_action"):
                interview_result = self.interview_service.execute_invitation_action(
                    user=user,
                    raw_message_id=raw_message_id,
                    action=stage_result.proposed_action,
                )
                if interview_result is None:
                    return None
                return [
                    self._notify_result(
                        user_id=user.id,
                        template_key=interview_result.notification_template,
                        text=interview_result.notification_text,
                        reply_markup=remove_keyboard()
                        if interview_result.status in {"accepted", "skipped"}
                        else None,
                    )
                ]
            text = (
                "Accept interview"
                if stage_result.proposed_action == "accept_interview"
                else "Skip opportunity"
            )
        elif (
            stage_result.stage == "INTERVIEW_IN_PROGRESS"
            and stage_result.proposed_action in {
                "answer_current_question",
                "accept_interview",
                "skip_opportunity",
                "cancel_interview",
            }
        ):
            interview_result = self.interview_service.execute_active_interview_action(
                user=user,
                raw_message_id=raw_message_id,
                action=stage_result.proposed_action,
                content_type=normalized_update.content_type,
                text=(stage_result.structured_payload or {}).get("answer_text") or normalized_update.text,
                file_id=file_id,
            )
            if interview_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=interview_result.notification_template,
                    text=interview_result.notification_text,
                    reply_markup=remove_keyboard()
                    if interview_result.status in {"accepted", "skipped"}
                    else None,
                )
            ]
        elif stage_result.stage != "INTERVIEW_IN_PROGRESS":
            return None
        return None

    def _handle_candidate_summary_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "SUMMARY_REVIEW"
            and stage_result.action_accepted
            and stage_result.proposed_action in {"approve_summary", "request_summary_change"}
        ):
            return None
        summary_input_text = (
            "Approve summary"
            if stage_result.proposed_action == "approve_summary"
            else (stage_result.structured_payload or {}).get("edit_text") or normalized_update.text
        )
        summary_review_result = self.candidate_service.execute_summary_review_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
            structured_payload={
                "edit_text": summary_input_text
            }
            if stage_result.proposed_action == "request_summary_change"
            else {},
        )
        if summary_review_result is None:
            return None
        message_map = {
            "candidate_summary_approved": "Good. Let’s lock in your preferences. What salary range would feel right for your next role?",
            "candidate_summary_edit_processing": "Got it. I’m tightening the summary now.",
            "candidate_summary_edit_limit_reached": "You’ve used the one edit pass here. Check the latest version and approve it if it looks right.",
            "candidate_summary_edit_empty": "Tell me exactly what looks off in the summary and I’ll fix it once.",
            "candidate_summary_not_available": "I don’t have a summary ready to review yet.",
            "candidate_summary_review_help": "If it looks right, approve it. If not, tell me what I should fix.",
        }
        return [
            self._notify_result(
                user_id=user.id,
                template_key=summary_review_result.notification_template,
                text=self._copy(message_map[summary_review_result.notification_template]),
                reply_markup=(
                    summary_review_keyboard(edit_allowed=True)
                    if summary_review_result.notification_template in {
                        "candidate_summary_review_help",
                        "candidate_summary_edit_empty",
                    }
                    else summary_review_keyboard(edit_allowed=False)
                    if summary_review_result.notification_template
                    == "candidate_summary_edit_limit_reached"
                    else remove_keyboard()
                    if summary_review_result.notification_template in {
                        "candidate_summary_approved",
                        "candidate_summary_edit_processing",
                    }
                    else None
                ),
            )
        ]

    def _handle_candidate_verification_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "VERIFICATION_PENDING"
            and stage_result.action_accepted
            and stage_result.proposed_action == "send_verification_video"
            and normalized_update.content_type == "video"
        ):
            return None
        verification_result = self.candidate_service.handle_verification_submission(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            file_id=file_id,
        )
        if verification_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=verification_result.notification_template,
                text=verification_result.notification_text,
                allow_duplicate=True,
            )
        ]

    def _handle_manager_clarification_stage_action(
        self,
        *,
        user,
        raw_message_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "CLARIFICATION_QA"
            and stage_result.action_accepted
            and stage_result.proposed_action == "send_vacancy_clarifications"
        ):
            return None
        clarification_result = self.vacancy_service.handle_clarification_parsed_payload(
            user=user,
            raw_message_id=raw_message_id,
            parsed_payload=stage_result.structured_payload or {},
        )
        if clarification_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=clarification_result.notification_template,
                text=self._copy(clarification_result.notification_text),
            )
        ]

    def _handle_manager_summary_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "VACANCY_SUMMARY_REVIEW"
            and stage_result.action_accepted
            and stage_result.proposed_action in {"approve_summary", "request_summary_change"}
        ):
            return None
        summary_input_text = (
            "Approve summary"
            if stage_result.proposed_action == "approve_summary"
            else (stage_result.structured_payload or {}).get("edit_text") or normalized_update.text
        )
        summary_review_result = self.vacancy_service.execute_summary_review_action(
            user=user,
            raw_message_id=raw_message_id,
            action=stage_result.proposed_action,
            structured_payload={
                "edit_text": summary_input_text
            }
            if stage_result.proposed_action == "request_summary_change"
            else {},
        )
        if summary_review_result is None:
            return None
        message_map = {
            "vacancy_summary_approved": "Good. Let’s lock in the basics. What budget range are you hiring with for this role?",
            "vacancy_summary_edit_processing": "Got it. I’m updating the vacancy summary now.",
            "vacancy_summary_edit_limit_reached": "You’ve used the one edit pass here. Check the latest version and approve it if it looks right.",
            "vacancy_summary_edit_empty": "Tell me exactly what looks off in the vacancy summary and I’ll fix it once.",
            "vacancy_summary_not_available": "I don’t have a vacancy summary ready to review yet.",
            "vacancy_summary_review_help": "If it looks right, approve it. If not, tell me what I should fix.",
        }
        return [
            self._notify_result(
                user_id=user.id,
                template_key=summary_review_result.notification_template,
                text=self._copy(message_map[summary_review_result.notification_template]),
                reply_markup=(
                    summary_review_keyboard(edit_allowed=True)
                    if summary_review_result.notification_template in {
                        "vacancy_summary_review_help",
                        "vacancy_summary_edit_empty",
                    }
                    else summary_review_keyboard(edit_allowed=False)
                    if summary_review_result.notification_template
                    == "vacancy_summary_edit_limit_reached"
                    else remove_keyboard()
                    if summary_review_result.notification_template in {
                        "vacancy_summary_approved",
                        "vacancy_summary_edit_processing",
                    }
                    else None
                ),
            )
        ]

    def _handle_manager_intake_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "INTAKE_PENDING"
            and stage_result.action_accepted
            and stage_result.proposed_action == "send_job_description_text"
        ):
            return None
        intake_result = self.vacancy_service.handle_jd_intake(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            text=(stage_result.structured_payload or {}).get("job_description_text") or normalized_update.text,
            file_id=file_id,
        )
        message_map = {
            "vacancy_jd_received_processing": "Nice, got it. I’m turning that into a vacancy summary now.",
            "manager_input_not_expected": "Manager input is not expected at the current step.",
            "manager_input_unsupported": "Send the JD as text, a file, voice, or video.",
        }
        return [
            self._notify_result(
                user_id=user.id,
                template_key=intake_result.notification_template,
                text=self._copy(message_map[intake_result.notification_template]),
            )
        ]

    def _handle_candidate_intake_stage_action(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if not (
            stage_result is not None
            and stage_result.stage == "CV_PENDING"
            and stage_result.action_accepted
            and stage_result.proposed_action == "send_cv_text"
        ):
            return None
        intake_result = self.candidate_service.handle_cv_intake(
            user=user,
            raw_message_id=raw_message_id,
            content_type="text",
            text=(stage_result.structured_payload or {}).get("cv_text") or normalized_update.text,
            file_id=file_id,
        )
        return [
            self._notify_result(
                user_id=user.id,
                template_key=intake_result.notification_template,
                text=self._candidate_cv_intake_message(
                    notification_template=intake_result.notification_template,
                    content_type="text",
                ),
            )
        ]

    def _handle_candidate_interview_message(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
    ) -> List[str] | None:
        interview_result = self.interview_service.execute_active_interview_action(
            user=user,
            raw_message_id=raw_message_id,
            action="answer_current_question",
            content_type=normalized_update.content_type,
            text=normalized_update.text,
            file_id=file_id,
        )
        if interview_result is None:
            interview_result = self.interview_service.execute_invitation_action(
                user=user,
                raw_message_id=raw_message_id,
                action=None,
            )
        if interview_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=interview_result.notification_template,
                text=interview_result.notification_text,
                reply_markup=remove_keyboard()
                if interview_result.status in {"accepted", "skipped"}
                else None,
            )
        ]

    def _handle_candidate_verification_message(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        file_id,
    ) -> List[str] | None:
        verification_result = self.candidate_service.handle_verification_submission(
            user=user,
            raw_message_id=raw_message_id,
            content_type=content_type,
            file_id=file_id,
        )
        if verification_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=verification_result.notification_template,
                text=verification_result.notification_text,
                allow_duplicate=True,
            )
        ]

    def _handle_candidate_questions_message(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
    ) -> List[str] | None:
        questions_result = self.candidate_service.handle_questions_answer(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            text=normalized_update.text,
            file_id=file_id,
        )
        if questions_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=questions_result.notification_template,
                text=questions_result.notification_text,
            )
        ]

    def _handle_manager_clarification_message(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
    ) -> List[str] | None:
        clarification_result = self.vacancy_service.handle_clarification_answer(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            text=normalized_update.text,
            file_id=file_id,
        )
        if clarification_result is None:
            return None
        return [
            self._notify_result(
                user_id=user.id,
                template_key=clarification_result.notification_template,
                text=self._copy(clarification_result.notification_text),
            )
        ]

    def _handle_manager_intake_message(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
    ) -> List[str]:
        intake_result = self.vacancy_service.handle_jd_intake(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            text=normalized_update.text,
            file_id=file_id,
        )
        message_map = {
            "vacancy_jd_received_processing": "Nice, got it. I’m turning that into a vacancy summary now.",
            "manager_input_not_expected": "Manager input is not expected at the current step.",
            "manager_input_unsupported": "Send the JD as text, a file, voice, or video.",
        }
        return [
            self._notify_result(
                user_id=user.id,
                template_key=intake_result.notification_template,
                text=self._copy(message_map[intake_result.notification_template]),
            )
        ]

    def _handle_candidate_intake_message(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
    ) -> List[str]:
        intake_result = self.candidate_service.handle_cv_intake(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            text=normalized_update.text,
            file_id=file_id,
        )
        return [
            self._notify_result(
                user_id=user.id,
                template_key=intake_result.notification_template,
                text=self._candidate_cv_intake_message(
                    notification_template=intake_result.notification_template,
                    content_type=normalized_update.content_type,
                ),
            )
        ]

    def _apply_candidate_delete_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        deletion_templates = self._handle_candidate_delete_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            stage_result=stage_result,
        )
        if deletion_templates is not None:
            return deletion_templates
        if stage_result is not None and stage_result.stage == "DELETE_CONFIRMATION":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=latest_user_message,
                user_id=user.id,
                stage_result=stage_result,
                reply_markup=deletion_confirmation_keyboard("candidate"),
            )
            if assistance_templates is not None:
                return assistance_templates
        return None

    def _apply_candidate_interview_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if normalized_update.content_type == "text":
            candidate_interaction_templates = self._handle_candidate_interaction_stage_action(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
                file_id=file_id,
                stage_result=stage_result,
            )
            if candidate_interaction_templates is not None:
                return candidate_interaction_templates
            if stage_result is not None and stage_result.stage in {"INTERVIEW_INVITED", "INTERVIEW_IN_PROGRESS"}:
                assistance_templates = self._maybe_handle_graph_help(
                    user=user,
                    latest_user_message=normalized_update.text or "",
                    user_id=user.id,
                    stage_result=stage_result,
                )
                if assistance_templates is not None:
                    return assistance_templates
            return None
        return self._handle_candidate_interview_message(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
        )

    def _apply_candidate_vacancy_review_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        templates = self._handle_candidate_vacancy_review_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            stage_result=stage_result,
        )
        if templates is not None:
            return templates
        if stage_result is not None and stage_result.stage == "VACANCY_REVIEW":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=latest_user_message,
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
        return None

    def _apply_candidate_summary_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        stage_result,
    ) -> List[str] | None:
        summary_templates = self._handle_candidate_summary_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            stage_result=stage_result,
        )
        if summary_templates is not None:
            return summary_templates
        assistance_templates = self._maybe_handle_graph_help(
            user=user,
            latest_user_message=normalized_update.text or "",
            user_id=user.id,
            stage_result=stage_result,
        )
        if assistance_templates is not None:
            return assistance_templates
        return None

    def _apply_candidate_verification_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        verification_templates = self._handle_candidate_verification_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
            stage_result=stage_result,
        )
        if verification_templates is not None:
            return verification_templates
        if normalized_update.content_type == "text":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or "",
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
        if normalized_update.content_type in {"voice", "document"}:
            return self._handle_candidate_verification_message(
                user=user,
                raw_message_id=raw_message_id,
                content_type=normalized_update.content_type,
                file_id=file_id,
            )
        return self._handle_candidate_verification_message(
            user=user,
            raw_message_id=raw_message_id,
            content_type=normalized_update.content_type,
            file_id=file_id,
        )

    def _apply_candidate_questions_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if (
            stage_result is not None
            and stage_result.stage == "QUESTIONS_PENDING"
            and stage_result.action_accepted
            and stage_result.proposed_action == "send_salary_location_work_format"
        ):
            questions_result = self.candidate_service.handle_questions_parsed_payload(
                user=user,
                raw_message_id=raw_message_id,
                parsed_payload=stage_result.structured_payload or {},
            )
            if questions_result is None:
                return None
            return [
                self._notify_result(
                    user_id=user.id,
                    template_key=questions_result.notification_template,
                    text=questions_result.notification_text,
                )
            ]
        if normalized_update.content_type == "text":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or "",
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
            return None
        return self._handle_candidate_questions_message(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
        )

    def _apply_candidate_intake_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str]:
        if stage_result is not None and stage_result.stage == "CV_PROCESSING":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or normalized_update.content_type,
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
            return None
        if normalized_update.content_type == "text":
            candidate_intake_templates = self._handle_candidate_intake_stage_action(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
                file_id=file_id,
                stage_result=stage_result,
            )
            if candidate_intake_templates is not None:
                return candidate_intake_templates
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or "",
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
            return None
        return self._handle_candidate_intake_message(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
        )

    def _apply_manager_delete_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        deletion_templates = self._handle_manager_delete_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            latest_user_message=latest_user_message,
            stage_result=stage_result,
        )
        if deletion_templates is not None:
            return deletion_templates
        if stage_result is not None and stage_result.stage == "DELETE_CONFIRMATION":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=latest_user_message,
                user_id=user.id,
                stage_result=stage_result,
                reply_markup=deletion_confirmation_keyboard("vacancy"),
            )
            if assistance_templates is not None:
                return assistance_templates
        return None

    def _apply_manager_review_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        manager_templates = self._handle_manager_review_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            stage_result=stage_result,
        )
        if manager_templates is not None:
            return manager_templates
        assistance_templates = self._maybe_handle_graph_help(
            user=user,
            latest_user_message=latest_user_message,
            user_id=user.id,
            stage_result=stage_result,
        )
        if assistance_templates is not None:
            return assistance_templates
        return None

    def _apply_manager_pre_interview_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        templates = self._handle_manager_pre_interview_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            latest_user_message=latest_user_message,
            stage_result=stage_result,
        )
        if templates is not None:
            return templates
        if stage_result is not None and stage_result.stage == "PRE_INTERVIEW_REVIEW":
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=latest_user_message,
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
        return None

    def _apply_manager_clarification_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        if normalized_update.content_type == "text":
            clarification_templates = self._handle_manager_clarification_stage_action(
                user=user,
                raw_message_id=raw_message_id,
                stage_result=stage_result,
            )
            if clarification_templates is not None:
                return clarification_templates
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or "",
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
            return None
        return self._handle_manager_clarification_message(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
        )

    def _apply_manager_summary_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        stage_result,
    ) -> List[str] | None:
        if normalized_update.content_type != "text":
            return None
        summary_templates = self._handle_manager_summary_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            stage_result=stage_result,
        )
        if summary_templates is not None:
            return summary_templates
        assistance_templates = self._maybe_handle_graph_help(
            user=user,
            latest_user_message=normalized_update.text or "",
            user_id=user.id,
            stage_result=stage_result,
            reply_markup=summary_review_keyboard(edit_allowed=True),
        )
        if assistance_templates is not None:
            return assistance_templates
        return None

    def _apply_manager_intake_segment(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str]:
        if normalized_update.content_type == "text":
            manager_intake_templates = self._handle_manager_intake_stage_action(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
                file_id=file_id,
                stage_result=stage_result,
            )
            if manager_intake_templates is not None:
                return manager_intake_templates
            assistance_templates = self._maybe_handle_graph_help(
                user=user,
                latest_user_message=normalized_update.text or "",
                user_id=user.id,
                stage_result=stage_result,
            )
            if assistance_templates is not None:
                return assistance_templates
            return None
        return self._handle_manager_intake_message(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
        )

    def _apply_candidate_flow(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        return self._dispatch_segment_chain(
            content_type=normalized_update.content_type,
            segments=[
                (
                    {"text"},
                    lambda: self._apply_candidate_delete_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "voice", "video"},
                    lambda: self._apply_candidate_interview_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_candidate_vacancy_review_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_candidate_summary_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "voice", "document", "video"},
                    lambda: self._apply_candidate_verification_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "voice", "video"},
                    lambda: self._apply_candidate_questions_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "document", "voice"},
                    lambda: self._apply_candidate_intake_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
            ],
        )

    def _apply_manager_flow(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        stage_result,
    ) -> List[str] | None:
        return self._dispatch_segment_chain(
            content_type=normalized_update.content_type,
            segments=[
                (
                    {"text"},
                    lambda: self._apply_manager_delete_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_manager_pre_interview_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_manager_open_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_manager_review_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        latest_user_message=normalized_update.text or "",
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text"},
                    lambda: self._apply_manager_summary_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "voice", "video"},
                    lambda: self._apply_manager_clarification_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
                (
                    {"text", "document", "voice", "video"},
                    lambda: self._apply_manager_intake_segment(
                        user=user,
                        raw_message_id=raw_message_id,
                        normalized_update=normalized_update,
                        file_id=file_id,
                        stage_result=stage_result,
                    ),
                ),
            ],
        )

    def _apply_manager_open_segment(
        self,
        *,
        user,
        raw_message_id,
        latest_user_message: str,
        stage_result,
    ) -> List[str] | None:
        action_templates = self._handle_manager_open_stage_action(
            user=user,
            raw_message_id=raw_message_id,
            latest_user_message=latest_user_message,
            stage_result=stage_result,
        )
        if action_templates is not None:
            return action_templates

        if stage_result is not None and stage_result.stage == "OPEN":
            return self._maybe_handle_graph_help(
                user=user,
                latest_user_message=latest_user_message,
                user_id=user.id,
                stage_result=stage_result,
            )
        return None

    def _resolve_recovery_context(self, *, user):
        if hasattr(self.stage_agents, "resolve_current_stage_context"):
            return self.stage_agents.resolve_current_stage_context(user=user)

        role = None
        if getattr(user, "is_candidate", False):
            role = "candidate"
        elif getattr(user, "is_hiring_manager", False):
            role = "hiring_manager"

        if not has_primary_contact_channel(user):
            return resolve_state_context(role=role, state="CONTACT_REQUIRED")
        if role is None:
            return resolve_state_context(role=None, state="ROLE_SELECTION")
        return resolve_state_context(role=role, state=None)

    def _build_generic_recovery_message(self, *, user, latest_user_message: str) -> str:
        context = self._resolve_recovery_context(user=user)
        if context.state == "CONTACT_REQUIRED":
            return context.guidance_text
        if context.state == "ROLE_SELECTION":
            return self.messaging.compose_role_selection(
                latest_user_message=latest_user_message or None,
            )
        return self.messaging.compose_recovery(
            state=context.state,
            allowed_actions=context.allowed_actions,
            latest_user_message=latest_user_message,
        )

    def _build_unsupported_input_templates(
        self,
        *,
        user,
        latest_user_message: str,
    ) -> List[str]:
        return [
            self._notify(
                user.id,
                "unsupported_input",
                {
                    "text": self._build_generic_recovery_message(
                        user=user,
                        latest_user_message=latest_user_message,
                    )
                },
            )
        ]

    def _apply_entry_flow(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        text_value: str,
    ) -> List[str] | None:
        if normalized_update.contact_phone_number:
            return self._handle_contact_share(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
            )

        should_offer_entry_assistance = (
            not has_primary_contact_channel(user)
            or (not user.is_candidate and not user.is_hiring_manager)
        )

        if should_offer_entry_assistance and normalized_update.content_type == "text":
            entry_result = self.stage_agents.maybe_run_entry_stage(
                user=user,
                latest_user_message=normalized_update.text or "",
                latest_message_type=normalized_update.content_type,
            )
            entry_templates = self._handle_entry_stage_result(
                user=user,
                raw_message_id=raw_message_id,
                entry_result=entry_result,
            )
            if entry_templates is not None:
                return entry_templates

        if text_value == "/start":
            return self._handle_start_command(user=user)

        return None

    def _maybe_run_candidate_stage_for_update(
        self,
        *,
        user,
        normalized_update: NormalizedTelegramUpdate,
    ):
        if not getattr(user, "is_candidate", False):
            return None
        if normalized_update.content_type not in {"text", "voice", "document", "video"}:
            return None
        return self._maybe_run_graph_stage(
            user=user,
            normalized_update=normalized_update,
        )

    def _maybe_run_manager_stage_for_update(
        self,
        *,
        user,
        normalized_update: NormalizedTelegramUpdate,
    ):
        if not getattr(user, "is_hiring_manager", False):
            return None
        if normalized_update.content_type != "text":
            return None
        return self._maybe_run_graph_stage(
            user=user,
            normalized_update=normalized_update,
        )

    def _precompute_role_stage_results(
        self,
        *,
        user,
        normalized_update: NormalizedTelegramUpdate,
    ):
        return (
            self._maybe_run_candidate_stage_for_update(
                user=user,
                normalized_update=normalized_update,
            ),
            self._maybe_run_manager_stage_for_update(
                user=user,
                normalized_update=normalized_update,
            ),
        )

    def _apply_role_flows(
        self,
        *,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        file_id,
        candidate_stage_result,
        manager_stage_result,
    ) -> List[str] | None:
        if user.is_candidate:
            candidate_templates = self._apply_candidate_flow(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
                file_id=file_id,
                stage_result=candidate_stage_result,
            )
            if candidate_templates is not None:
                return candidate_templates

        if user.is_hiring_manager:
            manager_templates = self._apply_manager_flow(
                user=user,
                raw_message_id=raw_message_id,
                normalized_update=normalized_update,
                file_id=file_id,
                stage_result=manager_stage_result,
            )
            if manager_templates is not None:
                return manager_templates

        return None

    def _create_raw_message_for_update(self, *, user_id, normalized_update: NormalizedTelegramUpdate):
        return self.raw_messages_repo.create(
            user_id=user_id,
            telegram_update_id=normalized_update.update_id,
            telegram_message_id=normalized_update.message_id,
            telegram_chat_id=normalized_update.telegram_chat_id,
            direction="inbound",
            content_type=normalized_update.content_type,
            payload_json=normalized_update.payload,
            text_content=normalized_update.text if normalized_update.content_type != "callback" else None,
        )

    def _build_processed_update_result(self, *, user_id, notification_templates: List[str]) -> ProcessedTelegramUpdate:
        return ProcessedTelegramUpdate(
            status="processed",
            deduplicated=False,
            notification_templates=notification_templates,
            user_id=str(user_id),
        )

    def _acknowledge_callback_query(self, normalized_update: NormalizedTelegramUpdate) -> None:
        callback_query_id = getattr(normalized_update, "callback_query_id", None)
        if not callback_query_id:
            return
        try:
            TelegramBotClient().answer_callback_query(callback_query_id=callback_query_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("telegram_callback_query_ack_failed", error=str(exc))

    def process(self, normalized_update: NormalizedTelegramUpdate) -> ProcessedTelegramUpdate:
        session_info = getattr(self.session, "info", None)
        if isinstance(session_info, dict):
            session_info["telegram_reply_chat_id"] = normalized_update.telegram_chat_id
        try:
            self.session.info["created_job_ids"] = []
            self.session.info["created_notification_ids"] = []
            existing = self.raw_messages_repo.get_by_update_id(normalized_update.update_id)
            if existing is not None:
                return ProcessedTelegramUpdate(
                    status="duplicate",
                    deduplicated=True,
                    notification_templates=[],
                    user_id=str(existing.user_id) if existing.user_id else "",
                )

            user = self.identity_service.ensure_user(normalized_update)
            raw_message = self._create_raw_message_for_update(
                user_id=user.id,
                normalized_update=normalized_update,
            )
            persisted_file = self._persist_file_if_present(user.id, raw_message, normalized_update)

            notification_templates = self._apply_identity_flow(
                user,
                raw_message.id,
                normalized_update,
                file_id=persisted_file.id if persisted_file is not None else None,
            )
            self.session.commit()
            self._flush_immediate_jobs()
            self._flush_immediate_notifications_for_user(user.id)
            self._acknowledge_callback_query(normalized_update)

            return self._build_processed_update_result(
                user_id=user.id,
                notification_templates=notification_templates,
            )
        finally:
            if isinstance(session_info, dict):
                session_info.pop("telegram_reply_chat_id", None)

    def _apply_identity_flow(
        self,
        user,
        raw_message_id,
        normalized_update: NormalizedTelegramUpdate,
        *,
        file_id=None,
    ) -> List[str]:
        callback_templates = self._handle_callback_action(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
        )
        if callback_templates is not None:
            return callback_templates

        text_value = normalize_command_text(normalized_update.text)

        entry_templates = self._apply_entry_flow(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            text_value=text_value,
        )
        if entry_templates is not None:
            return entry_templates

        candidate_stage_result, manager_stage_result = self._precompute_role_stage_results(
            user=user,
            normalized_update=normalized_update,
        )

        role_templates = self._apply_role_flows(
            user=user,
            raw_message_id=raw_message_id,
            normalized_update=normalized_update,
            file_id=file_id,
            candidate_stage_result=candidate_stage_result,
            manager_stage_result=manager_stage_result,
        )
        if role_templates is not None:
            return role_templates

        return self._build_unsupported_input_templates(
            user=user,
            latest_user_message=normalized_update.text or normalized_update.content_type,
        )

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
        if file_row.status == "received" and file_row.telegram_file_id:
            queue = DatabaseQueueClient(self.session)
            queue.enqueue(
                JobMessage(
                    job_type="file_store_telegram_v1",
                    idempotency_key=f"file:{file_row.id}:store",
                    payload={"file_id": str(file_row.id)},
                    entity_type="file",
                    entity_id=file_row.id,
                )
            )
            self.files_repo.mark_storage_queued(file_row)
        return file_row

    def _notify(self, user_id, template_key: str, payload: dict, *, allow_duplicate: bool = False) -> str:
        notification_payload = dict(payload or {})
        session_info = getattr(self.session, "info", None)
        if isinstance(session_info, dict):
            reply_chat_id = session_info.get("telegram_reply_chat_id")
            if reply_chat_id and "telegram_chat_id" not in notification_payload:
                notification_payload["telegram_chat_id"] = reply_chat_id
        self.notifications_repo.create(
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            template_key=template_key,
            payload_json=notification_payload,
            allow_duplicate=allow_duplicate,
        )
        return template_key

    def _flush_immediate_jobs(self) -> None:
        created_job_ids = list(self.session.info.pop("created_job_ids", []))
        if not created_job_ids:
            return
        try:
            repo = JobExecutionLogsRepository(self.session)
            queue_index = 0
            while queue_index < len(created_job_ids):
                job_id = created_job_ids[queue_index]
                queue_index += 1
                job = repo.claim_by_id_if_queued(job_id)
                if job is None:
                    continue
                if job.job_type not in self._safe_immediate_job_types:
                    continue
                repo.mark_started(job)
                result = process_job(self.session, job)
                repo.mark_completed(job, result_json=result)
                more_job_ids = self.session.info.pop("created_job_ids", [])
                for new_job_id in more_job_ids:
                    if new_job_id not in created_job_ids:
                        created_job_ids.append(new_job_id)
            self.session.commit()
        except Exception as exc:  # noqa: BLE001
            self.session.rollback()
            self.logger.warning(
                "telegram_immediate_job_flush_failed",
                job_count=len(created_job_ids),
                error=str(exc),
            )
            TelegramErrorAlertService().send_error_alert(
                source="telegram_immediate_job_flush",
                summary="Immediate job flush failed during Telegram webhook processing.",
                exc=exc,
                context={"job_count": len(created_job_ids)},
            )

    def _flush_immediate_notifications_for_user(self, user_id) -> None:
        notification_ids = list(self.session.info.pop("created_notification_ids", []))
        if not notification_ids:
            return
        try:
            self.notification_delivery.deliver_notification_ids(notification_ids)
            self.session.commit()
        except Exception as exc:  # noqa: BLE001
            self.session.rollback()
            self.logger.warning(
                "telegram_immediate_notification_flush_failed",
                notification_count=len(notification_ids),
                error=str(exc),
            )
            TelegramErrorAlertService().send_error_alert(
                source="telegram_immediate_notification_flush",
                summary="Immediate notification flush failed during Telegram webhook processing.",
                exc=exc,
                context={
                    "notification_count": len(notification_ids),
                    "user_id": str(user_id),
                },
            )
