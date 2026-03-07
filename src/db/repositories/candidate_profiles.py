from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models.candidates import CandidateProfile, CandidateProfileVersion


class CandidateProfilesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_by_user_id(self, user_id) -> Optional[CandidateProfile]:
        stmt = select(CandidateProfile).where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.deleted_at.is_(None),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, *, user_id, state: str) -> CandidateProfile:
        profile = CandidateProfile(user_id=user_id, state=state)
        self.session.add(profile)
        self.session.flush()
        return profile

    def set_state(self, profile: CandidateProfile, state: str) -> CandidateProfile:
        profile.state = state
        self.session.flush()
        return profile

    def next_version_no(self, profile_id) -> int:
        stmt = select(func.coalesce(func.max(CandidateProfileVersion.version_no), 0)).where(
            CandidateProfileVersion.profile_id == profile_id
        )
        current_max = self.session.execute(stmt).scalar_one()
        return int(current_max) + 1

    def create_version(
        self,
        *,
        profile_id,
        version_no: int,
        source_type: str,
        source_raw_message_id=None,
        extracted_text=None,
        transcript_text=None,
    ) -> CandidateProfileVersion:
        version = CandidateProfileVersion(
            profile_id=profile_id,
            version_no=version_no,
            source_type=source_type,
            source_raw_message_id=source_raw_message_id,
            extracted_text=extracted_text,
            transcript_text=transcript_text,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def set_current_version(self, profile: CandidateProfile, version_id) -> CandidateProfile:
        profile.current_version_id = version_id
        self.session.flush()
        return profile

