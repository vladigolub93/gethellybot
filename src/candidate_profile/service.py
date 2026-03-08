from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.candidate_profile.question_prompts import (
    QUESTION_KEYS,
    follow_up_prompt,
    initial_questions_prompt,
    missing_questions_prompt,
)
from src.candidate_profile.verification import build_verification_phrase
from src.candidate_profile.states import (
    CANDIDATE_STATE_CONSENTED,
    CANDIDATE_STATE_CONTACT_COLLECTED,
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_NEW,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_READY,
    CANDIDATE_STATE_ROLE_CONFIRMED,
    CANDIDATE_STATE_SUMMARY_REVIEW,
    CANDIDATE_STATE_VERIFICATION_PENDING,
)
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.llm.service import safe_build_deletion_confirmation, safe_parse_candidate_questions
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.shared.text import normalize_command_text


@dataclass(frozen=True)
class CandidateIntakeResult:
    status: str
    notification_template: str


@dataclass(frozen=True)
class CandidateSummaryReviewResult:
    status: str
    notification_template: str


@dataclass(frozen=True)
class CandidateQuestionsResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class CandidateVerificationResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class CandidateDeletionResult:
    status: str
    notification_template: str
    notification_text: str


class CandidateProfileService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = CandidateProfilesRepository(session)
        self.verifications = CandidateVerificationsRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matching = MatchingRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    def ensure_profile_for_user(self, user) -> object:
        profile = self.repo.get_active_by_user_id(user.id)
        if profile is not None:
            return profile

        profile = self.repo.create(user_id=user.id, state=CANDIDATE_STATE_NEW)
        self.state_service.record_transition(
            entity_type="candidate_profile",
            entity_id=profile.id,
            from_state=None,
            to_state=CANDIDATE_STATE_NEW,
            trigger_type="system",
            actor_user_id=user.id,
            metadata_json={"reason": "candidate profile created"},
        )
        return profile

    def start_onboarding(self, user, *, trigger_ref_id=None) -> object:
        profile = self.ensure_profile_for_user(user)

        if profile.state == CANDIDATE_STATE_NEW:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CONTACT_COLLECTED,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"reason": "contact already collected before candidate profile creation"},
            )

        if profile.state == CANDIDATE_STATE_CONTACT_COLLECTED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CONSENTED,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"reason": "consent already collected before candidate profile creation"},
            )

        if profile.state == CANDIDATE_STATE_CONSENTED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_ROLE_CONFIRMED,
                trigger_type="user_action",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"role": "candidate"},
            )

        if profile.state == CANDIDATE_STATE_ROLE_CONFIRMED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CV_PENDING,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
            )

        return profile

    def handle_cv_intake(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> CandidateIntakeResult:
        profile = self.ensure_profile_for_user(user)

        if profile.state != CANDIDATE_STATE_CV_PENDING:
            return CandidateIntakeResult(
                status="ignored",
                notification_template="candidate_input_not_expected",
            )

        source_type = {
            "text": "pasted_text",
            "document": "document_upload",
            "voice": "voice_description",
        }.get(content_type, "unsupported")

        if source_type == "unsupported":
            return CandidateIntakeResult(
                status="unsupported",
                notification_template="candidate_input_unsupported",
            )

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_CV_PROCESSING,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={"content_type": content_type},
        )

        version = self.repo.create_version(
            profile_id=profile.id,
            version_no=self.repo.next_version_no(profile.id),
            source_type=source_type,
            source_file_id=file_id,
            source_raw_message_id=raw_message_id,
            extracted_text=text if content_type == "text" else None,
            transcript_text=text if content_type == "voice" else None,
        )
        self.repo.set_current_version(profile, version.id)
        self.queue.enqueue(
            JobMessage(
                job_type="candidate_cv_extract_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                    "candidate_profile_version_id": str(version.id),
                    "source_type": source_type,
                },
                idempotency_key=f"candidate_cv_extract_v1:{version.id}",
                entity_type="candidate_profile_version",
                entity_id=version.id,
            )
        )

        return CandidateIntakeResult(
            status="accepted",
            notification_template="candidate_cv_received_processing",
        )

    def handle_summary_review_action(
        self,
        *,
        user,
        raw_message_id,
        text: Optional[str],
    ) -> Optional[CandidateSummaryReviewResult]:
        normalized_text = (text or "").strip()
        lowered = normalize_command_text(normalized_text)
        action = None
        payload: dict = {}
        if lowered in {"approve summary", "approve", "approve profile"}:
            action = "approve_summary"
        else:
            if lowered.startswith("edit summary:") or lowered.startswith("edit:"):
                normalized_text = normalized_text.split(":", 1)[1].strip()
            if lowered in {"change summary", "edit summary", "change", "edit"}:
                payload["needs_edit_details"] = True
            elif normalized_text:
                action = "request_summary_change"
                payload["edit_text"] = normalized_text
        return self.execute_summary_review_action(
            user=user,
            raw_message_id=raw_message_id,
            action=action,
            structured_payload=payload,
        )

    def execute_summary_review_action(
        self,
        *,
        user,
        raw_message_id,
        action: str | None,
        structured_payload: dict | None = None,
    ) -> Optional[CandidateSummaryReviewResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_SUMMARY_REVIEW:
            return None

        payload = dict(structured_payload or {})
        if action is None and not payload:
            return CandidateSummaryReviewResult(
                status="empty",
                notification_template="candidate_summary_review_help",
            )

        if action == "approve_summary":
            current_version = self.repo.get_current_version(profile)
            if current_version is None:
                return CandidateSummaryReviewResult(
                    status="missing",
                    notification_template="candidate_summary_not_available",
                )

            self.repo.mark_version_approved(current_version)
            self.repo.update_questions_context(profile, self._ensure_questions_context(profile))
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_QUESTIONS_PENDING,
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=user.id,
                metadata_json={"action": "approve_summary"},
            )
            return CandidateSummaryReviewResult(
                status="approved",
                notification_template="candidate_summary_approved",
            )

        correction_count = self.repo.count_versions_by_source_type(profile.id, "summary_user_edit")
        if correction_count >= 1:
            return CandidateSummaryReviewResult(
                status="limit_reached",
                notification_template="candidate_summary_edit_limit_reached",
            )

        if payload.get("needs_edit_details"):
            return CandidateSummaryReviewResult(
                status="awaiting_edit_details",
                notification_template="candidate_summary_edit_empty",
            )

        edit_text = (payload.get("edit_text") or "").strip()
        if not edit_text:
            return CandidateSummaryReviewResult(
                status="empty_edit",
                notification_template="candidate_summary_edit_empty",
            )

        current_version = self.repo.get_current_version(profile)
        if current_version is None:
            return CandidateSummaryReviewResult(
                status="missing",
                notification_template="candidate_summary_not_available",
            )

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_CV_PROCESSING,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={"action": "edit_summary"},
        )
        new_version = self.repo.create_version(
            profile_id=profile.id,
            version_no=self.repo.next_version_no(profile.id),
            source_type="summary_user_edit",
            source_raw_message_id=raw_message_id,
            summary_json={
                "edit_request_text": edit_text,
                "base_version_id": str(current_version.id),
            },
            normalization_json={"edit_request_text": edit_text},
        )
        self.repo.set_current_version(profile, new_version.id)
        self.queue.enqueue(
            JobMessage(
                job_type="candidate_summary_edit_apply_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                    "candidate_profile_version_id": str(new_version.id),
                    "base_version_id": str(current_version.id),
                    "edit_request_text": edit_text,
                },
                idempotency_key=f"candidate_summary_edit_apply_v1:{new_version.id}",
                entity_type="candidate_profile_version",
                entity_id=new_version.id,
            )
        )
        return CandidateSummaryReviewResult(
            status="accepted",
            notification_template="candidate_summary_edit_processing",
        )

    def handle_questions_answer(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> Optional[CandidateQuestionsResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_QUESTIONS_PENDING:
            return None

        if content_type == "text":
            return self._apply_question_answer_text(
                profile=profile,
                raw_message_id=raw_message_id,
                text=text,
                actor_user_id=user.id,
                trigger_type="user_action",
            )

        if content_type in {"voice", "video"}:
            self.queue.enqueue(
                JobMessage(
                    job_type="candidate_questions_parse_v1",
                    payload={
                        "candidate_profile_id": str(profile.id),
                        "raw_message_id": str(raw_message_id),
                        "file_id": str(file_id) if file_id is not None else None,
                        "content_type": content_type,
                    },
                    idempotency_key=f"candidate_questions_parse_v1:{raw_message_id}",
                    entity_type="candidate_profile",
                    entity_id=profile.id,
                )
            )
            return CandidateQuestionsResult(
                status="queued",
                notification_template="candidate_questions_processing",
                notification_text="Answer received. Processing your mandatory profile details.",
            )

        return CandidateQuestionsResult(
            status="unsupported",
            notification_template="candidate_questions_unsupported",
            notification_text="Please answer with text, voice, or video.",
        )

    def process_question_answer_text(
        self,
        *,
        profile,
        raw_message_id,
        text: Optional[str],
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        return self._apply_question_answer_text(
            profile=profile,
            raw_message_id=raw_message_id,
            text=text,
            actor_user_id=actor_user_id,
            trigger_type=trigger_type,
        )

    def handle_questions_parsed_payload(
        self,
        *,
        user,
        raw_message_id,
        parsed_payload: dict,
    ) -> Optional[CandidateQuestionsResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_QUESTIONS_PENDING:
            return None
        return self._apply_question_payload(
            profile=profile,
            raw_message_id=raw_message_id,
            parsed=dict(parsed_payload or {}),
            actor_user_id=user.id,
            trigger_type="user_action",
        )

    def _apply_question_answer_text(
        self,
        *,
        profile,
        raw_message_id,
        text: Optional[str],
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return CandidateQuestionsResult(
                status="empty",
                notification_template="candidate_questions_help",
                notification_text=initial_questions_prompt(),
            )

        llm_result = safe_parse_candidate_questions(self.session, normalized_text)
        parsed = dict(llm_result.payload or {})
        return self._apply_question_payload(
            profile=profile,
            raw_message_id=raw_message_id,
            parsed=parsed,
            actor_user_id=actor_user_id,
            trigger_type=trigger_type,
        )

    def _apply_question_payload(
        self,
        *,
        profile,
        raw_message_id,
        parsed: dict,
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        if parsed:
            self.repo.update_question_answers(profile, **parsed)

        missing_keys = self._missing_question_keys(profile)
        if not missing_keys:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_VERIFICATION_PENDING,
                trigger_type=trigger_type,
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"action": "mandatory_questions_completed"},
            )
            verification = self._issue_verification(profile)
            return CandidateQuestionsResult(
                status="completed",
                notification_template="candidate_questions_completed",
                notification_text=(
                    "Mandatory profile questions completed. "
                    f"Please record a short video and say: '{verification.phrase_text}'."
                ),
            )

        questions_context = self._ensure_questions_context(profile)
        question_key = self._next_follow_up_key(questions_context, missing_keys)
        if question_key is not None:
            questions_context["follow_up_used"][question_key] = True
            self.repo.update_questions_context(profile, questions_context)
            return CandidateQuestionsResult(
                status="follow_up",
                notification_template="candidate_questions_follow_up",
                notification_text=follow_up_prompt(question_key),
            )

        return CandidateQuestionsResult(
            status="incomplete",
            notification_template="candidate_questions_missing",
            notification_text=missing_questions_prompt(missing_keys),
        )

    def _missing_question_keys(self, profile) -> list[str]:
        missing = []
        salary_min = getattr(profile, "salary_min", None)
        salary_max = getattr(profile, "salary_max", None)
        location_text = getattr(profile, "location_text", None)
        work_format = getattr(profile, "work_format", None)
        if salary_min is None and salary_max is None:
            missing.append("salary")
        if not location_text:
            missing.append("location")
        if not work_format:
            missing.append("work_format")
        return missing

    def _ensure_questions_context(self, profile) -> dict:
        current = dict(profile.questions_context_json or {})
        follow_up_used = dict(current.get("follow_up_used") or {})
        for key in QUESTION_KEYS:
            follow_up_used.setdefault(key, False)
        current["follow_up_used"] = follow_up_used
        return current

    def _next_follow_up_key(self, questions_context: dict, missing_keys: list[str]) -> Optional[str]:
        follow_up_used = questions_context.get("follow_up_used") or {}
        for key in missing_keys:
            if not follow_up_used.get(key, False):
                return key
        return None

    def handle_deletion_message(
        self,
        *,
        user,
        raw_message_id,
        text: Optional[str],
    ) -> Optional[CandidateDeletionResult]:
        profile = self.repo.get_active_by_user_id(user.id)
        if profile is None:
            return None

        normalized_text = normalize_command_text(text)
        deletion_context = self._ensure_deletion_context(profile)
        pending = bool(deletion_context.get("pending"))

        if normalized_text in {"cancel delete", "keep profile", "don't delete", "dont delete"} and pending:
            deletion_context["pending"] = False
            self._update_deletion_context(profile, deletion_context)
            return CandidateDeletionResult(
                status="cancelled",
                notification_template="candidate_deletion_cancelled",
                notification_text=self._copy("Profile deletion cancelled. Your profile remains active."),
            )

        if normalized_text not in {
            "delete profile",
            "delete my profile",
            "remove profile",
            "confirm delete",
            "confirm delete profile",
        }:
            return None

        active_matches = self.matching.list_active_for_candidate(profile.id)
        has_active_interview = any(
            self.interviews.get_active_by_match_id(match.id) is not None for match in active_matches
        )

        if normalized_text in {"confirm delete", "confirm delete profile"} and pending:
            return self._execute_deletion(
                profile=profile,
                raw_message_id=raw_message_id,
                actor_user_id=user.id,
                active_matches=active_matches,
            )

        deletion_context["pending"] = True
        self._update_deletion_context(profile, deletion_context)
        confirmation = safe_build_deletion_confirmation(
            self.session,
            entity_type="candidate_profile",
            has_active_interview=has_active_interview,
            has_active_matches=bool(active_matches),
        )
        return CandidateDeletionResult(
            status="confirmation_required",
            notification_template="candidate_deletion_confirmation_required",
            notification_text=confirmation.payload["message"],
        )

    def _ensure_deletion_context(self, profile) -> dict:
        current = dict(profile.questions_context_json or {})
        deletion = dict(current.get("deletion") or {})
        deletion.setdefault("pending", False)
        current["deletion"] = deletion
        return current

    def _update_deletion_context(self, profile, context: dict) -> None:
        self.repo.update_questions_context(profile, context)

    def _execute_deletion(self, *, profile, raw_message_id, actor_user_id, active_matches) -> CandidateDeletionResult:
        deletion_context = self._ensure_deletion_context(profile)
        deletion_context["pending"] = False
        self._update_deletion_context(profile, deletion_context)

        cancelled_matches = 0
        cancelled_interviews = 0
        for match in active_matches:
            session = self.interviews.get_active_by_match_id(match.id)
            if session is not None:
                self.state_service.transition(
                    entity_type="interview_session",
                    entity=session,
                    to_state="CANCELLED",
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=actor_user_id,
                    metadata_json={"reason": "candidate_deleted"},
                )
                cancelled_interviews += 1
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="cancelled",
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"reason": "candidate_deleted"},
                state_field="status",
            )
            cancelled_matches += 1

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state="DELETED",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=actor_user_id,
            metadata_json={
                "cancelled_matches": cancelled_matches,
                "cancelled_interviews": cancelled_interviews,
            },
        )
        self.repo.soft_delete(profile)
        self.queue.enqueue(
            JobMessage(
                job_type="cleanup_candidate_deletion_v1",
                payload={"candidate_profile_id": str(profile.id)},
                idempotency_key=f"cleanup_candidate_deletion_v1:{profile.id}",
                entity_type="candidate_profile",
                entity_id=profile.id,
            )
        )
        details = []
        if cancelled_matches:
            details.append(f"{cancelled_matches} active match(es)")
        if cancelled_interviews:
            details.append(f"{cancelled_interviews} interview(s)")
        details_text = ""
        if details:
            details_text = " Cancelled: " + ", ".join(details) + "."
        return CandidateDeletionResult(
            status="deleted",
            notification_template="candidate_deleted",
            notification_text=self._copy(f"Your profile has been deleted and removed from active recruiting flow.{details_text}"),
        )

    def handle_verification_submission(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        file_id=None,
    ) -> Optional[CandidateVerificationResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_VERIFICATION_PENDING:
            return None

        verification = self.verifications.get_pending_by_profile_id(profile.id)
        if verification is None:
            verification = self._issue_verification(profile)

        if content_type != "video" or file_id is None:
            return CandidateVerificationResult(
                status="instruction",
                notification_template="candidate_verification_instructions",
                notification_text=(
                    "Please send a short video and clearly say: "
                    f"'{verification.phrase_text}'."
                ),
            )

        self.verifications.mark_submitted(verification, video_file_id=file_id)
        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_READY,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={
                "action": "verification_submitted",
                "candidate_verification_id": str(verification.id),
            },
        )
        self.repo.mark_ready(profile)
        self.queue.enqueue(
            JobMessage(
                job_type="matching_candidate_ready_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                },
                idempotency_key=f"matching_candidate_ready_v1:{profile.id}",
                entity_type="candidate_profile",
                entity_id=profile.id,
            )
        )
        return CandidateVerificationResult(
            status="completed",
            notification_template="candidate_ready",
            notification_text="Video verification received. Your profile is now ready for matching.",
        )

    def _issue_verification(self, profile):
        existing = self.verifications.get_pending_by_profile_id(profile.id)
        if existing is not None:
            return existing

        attempt_no = self.verifications.next_attempt_no(profile.id)
        phrase_text = build_verification_phrase(
            profile_id=profile.id,
            attempt_no=attempt_no,
        )
        return self.verifications.create(
            profile_id=profile.id,
            attempt_no=attempt_no,
            phrase_text=phrase_text,
        )
