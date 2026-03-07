from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.candidate_profile.states import (
    CANDIDATE_STATE_CONSENTED,
    CANDIDATE_STATE_CONTACT_COLLECTED,
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_NEW,
    CANDIDATE_STATE_ROLE_CONFIRMED,
)
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.state.service import StateService


@dataclass(frozen=True)
class CandidateIntakeResult:
    status: str
    notification_template: str


class CandidateProfileService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = CandidateProfilesRepository(session)
        self.state_service = StateService(session)

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
            source_raw_message_id=raw_message_id,
            extracted_text=text if content_type == "text" else None,
            transcript_text=text if content_type == "voice" else None,
        )
        self.repo.set_current_version(profile, version.id)

        return CandidateIntakeResult(
            status="accepted",
            notification_template="candidate_cv_received_processing",
        )
