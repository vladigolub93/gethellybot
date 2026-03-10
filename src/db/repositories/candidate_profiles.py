from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.candidate_profile.states import CANDIDATE_READY_LIKE_STATES
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

    def get_ready_profiles(self) -> list[CandidateProfile]:
        stmt = select(CandidateProfile).where(
            CandidateProfile.state.in_(tuple(CANDIDATE_READY_LIKE_STATES)),
            CandidateProfile.deleted_at.is_(None),
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_top_similar_ready_profiles(self, *, embedding: list[float], limit: int = 50) -> list[dict]:
        distance_expr = CandidateProfileVersion.semantic_embedding.cosine_distance(embedding)
        stmt = (
            select(
                CandidateProfile,
                CandidateProfileVersion,
                distance_expr.label("distance"),
            )
            .join(
                CandidateProfileVersion,
                CandidateProfile.current_version_id == CandidateProfileVersion.id,
            )
            .where(
                CandidateProfile.state.in_(tuple(CANDIDATE_READY_LIKE_STATES)),
                CandidateProfile.deleted_at.is_(None),
                CandidateProfileVersion.semantic_embedding.is_not(None),
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )
        rows = self.session.execute(stmt).all()
        results: list[dict] = []
        for candidate, version, distance in rows:
            similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            results.append(
                {
                    "candidate": candidate,
                    "candidate_version": version,
                    "embedding_score": round(similarity, 4),
                }
            )
        return results

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

    def update_questions_context(self, profile: CandidateProfile, questions_context_json: dict) -> CandidateProfile:
        profile.questions_context_json = questions_context_json
        self.session.flush()
        return profile

    def update_question_answers(
        self,
        profile: CandidateProfile,
        *,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        location_text=None,
        country_code=None,
        city=None,
        work_format=None,
    ) -> CandidateProfile:
        if salary_min is not None:
            profile.salary_min = salary_min
        if salary_max is not None:
            profile.salary_max = salary_max
        if salary_currency is not None:
            profile.salary_currency = salary_currency
        if salary_period is not None:
            profile.salary_period = salary_period
        if location_text is not None:
            profile.location_text = location_text
        if country_code is not None:
            profile.country_code = country_code
        if city is not None:
            profile.city = city
        if work_format is not None:
            profile.work_format = work_format
        self.session.flush()
        return profile

    def mark_ready(self, profile: CandidateProfile) -> CandidateProfile:
        profile.ready_at = datetime.now(timezone.utc)
        self.session.flush()
        return profile

    def soft_delete(self, profile: CandidateProfile) -> CandidateProfile:
        profile.deleted_at = datetime.now(timezone.utc)
        profile.state = "DELETED"
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

    def update_version_source_text(
        self,
        version: CandidateProfileVersion,
        *,
        extracted_text=None,
        transcript_text=None,
    ) -> CandidateProfileVersion:
        if extracted_text is not None:
            version.extracted_text = extracted_text
        if transcript_text is not None:
            version.transcript_text = transcript_text
        self.session.flush()
        return version

    def update_version_embedding(
        self,
        version: CandidateProfileVersion,
        *,
        semantic_embedding: Optional[list[float]],
    ) -> CandidateProfileVersion:
        version.semantic_embedding = semantic_embedding
        self.session.flush()
        return version

    def count_versions_by_source_type(self, profile_id, source_type: str) -> int:
        stmt = select(func.count(CandidateProfileVersion.id)).where(
            CandidateProfileVersion.profile_id == profile_id,
            CandidateProfileVersion.source_type == source_type,
        )
        count = self.session.execute(stmt).scalar_one()
        return int(count)
