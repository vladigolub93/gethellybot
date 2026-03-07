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

    def get_by_id(self, profile_id) -> Optional[CandidateProfile]:
        stmt = select(CandidateProfile).where(CandidateProfile.id == profile_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_version_by_id(self, version_id) -> Optional[CandidateProfileVersion]:
        stmt = select(CandidateProfileVersion).where(CandidateProfileVersion.id == version_id)
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
        source_file_id=None,
        source_raw_message_id=None,
        extracted_text=None,
        transcript_text=None,
        summary_json=None,
        normalization_json=None,
        approval_status="draft",
        approved_by_user=False,
        prompt_version=None,
        model_name=None,
    ) -> CandidateProfileVersion:
        version = CandidateProfileVersion(
            profile_id=profile_id,
            version_no=version_no,
            source_type=source_type,
            source_file_id=source_file_id,
            source_raw_message_id=source_raw_message_id,
            extracted_text=extracted_text,
            transcript_text=transcript_text,
            summary_json=summary_json,
            normalization_json=normalization_json,
            approval_status=approval_status,
            approved_by_user=approved_by_user,
            prompt_version=prompt_version,
            model_name=model_name,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def set_current_version(self, profile: CandidateProfile, version_id) -> CandidateProfile:
        profile.current_version_id = version_id
        self.session.flush()
        return profile

    def get_current_version(self, profile: CandidateProfile) -> Optional[CandidateProfileVersion]:
        if profile.current_version_id is None:
            return None
        return self.get_version_by_id(profile.current_version_id)

    def update_version_analysis(
        self,
        version: CandidateProfileVersion,
        *,
        summary_json=None,
        normalization_json=None,
        approval_status: Optional[str] = None,
        approved_by_user: Optional[bool] = None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> CandidateProfileVersion:
        if summary_json is not None:
            version.summary_json = summary_json
        if normalization_json is not None:
            version.normalization_json = normalization_json
        if approval_status is not None:
            version.approval_status = approval_status
        if approved_by_user is not None:
            version.approved_by_user = approved_by_user
        if prompt_version is not None:
            version.prompt_version = prompt_version
        if model_name is not None:
            version.model_name = model_name
        self.session.flush()
        return version

    def mark_version_approved(self, version: CandidateProfileVersion) -> CandidateProfileVersion:
        version.approval_status = "approved"
        version.approved_by_user = True
        self.session.flush()
        return version

    def count_versions_by_source_type(self, profile_id, source_type: str) -> int:
        stmt = select(func.count(CandidateProfileVersion.id)).where(
            CandidateProfileVersion.profile_id == profile_id,
            CandidateProfileVersion.source_type == source_type,
        )
        count = self.session.execute(stmt).scalar_one()
        return int(count)
