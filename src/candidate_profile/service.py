from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.candidate_profile.states import (
    CANDIDATE_STATE_CONSENTED,
    CANDIDATE_STATE_CONTACT_COLLECTED,
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_NEW,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_ROLE_CONFIRMED,
    CANDIDATE_STATE_SUMMARY_REVIEW,
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
