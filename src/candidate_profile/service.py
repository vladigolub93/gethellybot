from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.candidate_profile.question_parser import parse_candidate_questions
from src.candidate_profile.question_prompts import (
    QUESTION_KEYS,
    follow_up_prompt,
    initial_questions_prompt,
    missing_questions_prompt,
)
from src.candidate_profile.states import (
    CANDIDATE_STATE_CONSENTED,
    CANDIDATE_STATE_CONTACT_COLLECTED,
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_NEW,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_ROLE_CONFIRMED,
    CANDIDATE_STATE_SUMMARY_REVIEW,
    CANDIDATE_STATE_VERIFICATION_PENDING,
)
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.state.service import StateService


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


class CandidateProfileService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = CandidateProfilesRepository(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)

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
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_SUMMARY_REVIEW:
            return None

        normalized_text = (text or "").strip()
        if not normalized_text:
            return CandidateSummaryReviewResult(
                status="empty",
                notification_template="candidate_summary_review_help",
            )

        lowered = normalized_text.lower()
        if lowered in {"approve summary", "approve", "approve profile"}:
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

        if lowered.startswith("edit summary:") or lowered.startswith("edit:"):
            edit_text = normalized_text.split(":", 1)[1].strip()
            if not edit_text:
                return CandidateSummaryReviewResult(
                    status="empty_edit",
                    notification_template="candidate_summary_edit_empty",
                )

            correction_count = self.repo.count_versions_by_source_type(profile.id, "summary_user_edit")
            if correction_count >= 3:
                return CandidateSummaryReviewResult(
                    status="limit_reached",
                    notification_template="candidate_summary_edit_limit_reached",
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

        return CandidateSummaryReviewResult(
            status="unsupported",
            notification_template="candidate_summary_review_help",
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

        parsed = parse_candidate_questions(normalized_text)
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
            return CandidateQuestionsResult(
                status="completed",
                notification_template="candidate_questions_completed",
                notification_text="Mandatory profile questions completed. Next step is video verification.",
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
        if profile.salary_min is None and profile.salary_max is None:
            missing.append("salary")
        if not profile.location_text:
            missing.append("location")
        if not profile.work_format:
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
