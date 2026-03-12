from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from src.candidate_profile.skills_inventory import candidate_version_full_hard_skills, display_skill_list
from src.cv_challenge.service import CandidateCvChallengeService
from src.config.settings import get_settings
from src.db.models.core import User
from src.db.models.matching import Match
from src.db.models.vacancies import Vacancy
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.users import UsersRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.shared.hiring_taxonomy import display_domains, display_english_level, display_hiring_stages
from src.webapp.auth import TelegramWebAppAuthError, verify_telegram_webapp_init_data
from src.webapp.presenters import (
    candidate_summary_snapshot,
    evaluation_snapshot,
    format_money_range,
    interview_state_label,
    isoformat_or_none,
    match_requires_action,
    match_status_description,
    match_status_label,
    source_text_snapshot,
    vacancy_summary_snapshot,
)
from src.webapp.session import (
    WebAppSessionContext,
    WebAppSessionError,
    issue_webapp_session_token,
    verify_webapp_session_token,
)


WEBAPP_ROLE_CANDIDATE = "candidate"
WEBAPP_ROLE_HIRING_MANAGER = "hiring_manager"
WEBAPP_ROLE_ADMIN = "admin"
WEBAPP_ROLE_UNKNOWN = "unknown"

WEBAPP_STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebAppService:
    INTERVIEW_RELATED_MATCH_STATUSES = frozenset(
        {
            "manager_interview_requested",
            "interview_queued",
            "invited",
            "accepted",
            "candidate_declined_interview",
            "interview_completed",
        }
    )

    def __init__(self, session):
        self.session = session
        self.settings = get_settings()
        self.users = UsersRepository(session)
        self.candidate_profiles = CandidateProfilesRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.matches = MatchingRepository(session)
        self.interviews = InterviewsRepository(session)
        self.evaluations = EvaluationsRepository(session)
        self.cv_challenge = CandidateCvChallengeService(session)

    def authenticate_init_data(self, init_data: str) -> Dict[str, Any]:
        try:
            identity = verify_telegram_webapp_init_data(
                init_data=init_data,
                bot_token=self.settings.telegram_bot_token,
                max_age_seconds=self.settings.telegram_webapp_auth_max_age_seconds,
            )
        except TelegramWebAppAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            )

        session_context = self._build_session_context(identity.telegram_user_id, identity.display_name or identity.username)
        try:
            token = issue_webapp_session_token(
                session_context=session_context,
                secret=self.settings.webapp_session_secret,
            )
        except WebAppSessionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        return {
            "sessionToken": token,
            "session": session_context.to_public_dict(),
        }

    def get_session_from_auth_header(self, authorization_header: str) -> WebAppSessionContext:
        token = self._extract_bearer_token(authorization_header)
        try:
            return verify_webapp_session_token(
                token=token,
                secret=self.settings.webapp_session_secret,
            )
        except WebAppSessionError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            )

    def build_session_payload(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        return {
            "session": session_context.to_public_dict(),
            "capabilities": self._capabilities_for_role(session_context.role),
        }

    def list_candidate_opportunities(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        user_id = self._require_session_user_id(session_context)
        profile = self._require_candidate_profile(session_context)
        current_version = self.candidate_profiles.get_current_version(profile)
        matches = sorted(
            self.matches.list_all_for_candidate(profile.id),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        items = [self._serialize_candidate_opportunity_card(match) for match in matches]
        return {
            "profile": self._serialize_candidate_profile(profile, current_version),
            "cvChallenge": self.cv_challenge.build_dashboard_card(user_id),
            "items": items,
        }

    def bootstrap_candidate_cv_challenge(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        user_id = self._require_session_user_id(session_context)
        response = self.cv_challenge.bootstrap_for_candidate(user_id)
        if response.get("eligible"):
            self.session.commit()
        return response

    def finish_candidate_cv_challenge(
        self,
        session_context: WebAppSessionContext,
        *,
        attempt_id: str,
        score: int,
        lives_left: int,
        stage_reached: int,
        won: bool,
        result_json: Optional[dict] = None,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        user_id = self._require_session_user_id(session_context)
        response = self.cv_challenge.finish_attempt(
            user_id=user_id,
            attempt_id=attempt_id,
            score=score,
            lives_left=lives_left,
            stage_reached=stage_reached,
            won=won,
            result_json=result_json,
        )
        self.session.commit()
        return response

    def save_candidate_cv_challenge_progress(
        self,
        session_context: WebAppSessionContext,
        *,
        attempt_id: str,
        score: int,
        lives_left: int,
        stage_reached: int,
        progress_json: Optional[dict] = None,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        user_id = self._require_session_user_id(session_context)
        response = self.cv_challenge.save_attempt_progress(
            user_id=user_id,
            attempt_id=attempt_id,
            score=score,
            lives_left=lives_left,
            stage_reached=stage_reached,
            progress_json=progress_json,
        )
        self.session.commit()
        return response

    def get_candidate_opportunity_detail(
        self,
        session_context: WebAppSessionContext,
        match_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        profile = self._require_candidate_profile(session_context)
        match = self._require_match(match_id)
        if str(match.candidate_profile_id) != str(profile.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        return self._serialize_match_detail(match, session_context=session_context)

    def get_candidate_profile_detail(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_CANDIDATE})
        profile = self._require_candidate_profile(session_context)
        current_version = self.candidate_profiles.get_current_version(profile)
        user = self.users.get_by_id(profile.user_id)
        return {
            "profile": self._serialize_candidate_profile_detail(
                profile,
                current_version,
                candidate_user=user,
                include_identity=True,
            ),
        }

    def list_manager_vacancies(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_HIRING_MANAGER})
        user_id = self._require_session_user_id(session_context)
        vacancies = sorted(
            self.vacancies.get_by_manager_user_id(user_id),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return {
            "items": [self._serialize_vacancy_card(vacancy) for vacancy in vacancies],
        }

    def get_manager_vacancy_detail(
        self,
        session_context: WebAppSessionContext,
        vacancy_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_HIRING_MANAGER})
        vacancy = self._require_owned_vacancy(session_context, vacancy_id)
        return self._serialize_vacancy_detail(vacancy)

    def list_manager_vacancy_matches(
        self,
        session_context: WebAppSessionContext,
        vacancy_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_HIRING_MANAGER})
        vacancy = self._require_owned_vacancy(session_context, vacancy_id)
        matches = sorted(
            self.matches.list_all_for_vacancy(vacancy.id),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return {
            "items": [self._serialize_manager_match_card(match) for match in matches],
        }

    def get_manager_match_detail(
        self,
        session_context: WebAppSessionContext,
        match_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_HIRING_MANAGER})
        match = self._require_match(match_id)
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found.")
        self._assert_manager_owns_vacancy(session_context, vacancy)
        return self._serialize_match_detail(match, session_context=session_context)

    def list_admin_vacancies(self, session_context: WebAppSessionContext) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_ADMIN})
        stmt = (
            select(Vacancy)
            .where(Vacancy.deleted_at.is_(None))
            .order_by(Vacancy.updated_at.desc(), Vacancy.created_at.desc())
        )
        vacancies = list(self.session.execute(stmt).scalars().all())
        return {
            "items": [self._serialize_vacancy_card(vacancy, include_manager=True) for vacancy in vacancies],
        }

    def get_admin_vacancy_detail(
        self,
        session_context: WebAppSessionContext,
        vacancy_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_ADMIN})
        vacancy = self._require_vacancy(vacancy_id)
        return self._serialize_vacancy_detail(vacancy, include_manager=True)

    def list_admin_vacancy_matches(
        self,
        session_context: WebAppSessionContext,
        vacancy_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_ADMIN})
        vacancy = self._require_vacancy(vacancy_id)
        matches = sorted(
            self.matches.list_all_for_vacancy(vacancy.id),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return {
            "items": [self._serialize_manager_match_card(match) for match in matches],
        }

    def get_admin_match_detail(
        self,
        session_context: WebAppSessionContext,
        match_id: str,
    ) -> Dict[str, Any]:
        self._require_role(session_context, {WEBAPP_ROLE_ADMIN})
        match = self._require_match(match_id)
        return self._serialize_match_detail(match, session_context=session_context)

    def _build_session_context(
        self,
        telegram_user_id: int,
        fallback_display_name: Optional[str],
    ) -> WebAppSessionContext:
        user = self.users.get_by_telegram_user_id(telegram_user_id)
        role = self._resolve_role(user, telegram_user_id)
        now_ts = int(time.time())
        return WebAppSessionContext(
            telegram_user_id=telegram_user_id,
            role=role,
            user_id=str(user.id) if user is not None else None,
            display_name=self._display_name(user, fallback_display_name),
            issued_at=now_ts,
            expires_at=now_ts + self.settings.telegram_webapp_session_ttl_seconds,
        )

    def _resolve_role(self, user: Optional[User], telegram_user_id: int) -> str:
        if user is None:
            return WEBAPP_ROLE_UNKNOWN
        if getattr(user, "is_hiring_manager", False):
            return WEBAPP_ROLE_HIRING_MANAGER
        if getattr(user, "is_candidate", False):
            return WEBAPP_ROLE_CANDIDATE
        candidate_profile = self.candidate_profiles.get_active_by_user_id(user.id)
        if candidate_profile is not None:
            return WEBAPP_ROLE_CANDIDATE
        latest_vacancy = self.vacancies.get_latest_active_by_manager_user_id(user.id)
        if latest_vacancy is not None:
            return WEBAPP_ROLE_HIRING_MANAGER
        return WEBAPP_ROLE_UNKNOWN

    @staticmethod
    def _display_name(user: Optional[User], fallback_display_name: Optional[str]) -> Optional[str]:
        if user is None:
            return fallback_display_name
        return getattr(user, "display_name", None) or getattr(user, "username", None) or fallback_display_name

    @staticmethod
    def _extract_bearer_token(authorization_header: str) -> str:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token is required.",
            )
        token = authorization_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token is required.",
            )
        return token

    @staticmethod
    def _capabilities_for_role(role: str) -> Dict[str, bool]:
        return {
            "candidateDashboard": role == WEBAPP_ROLE_CANDIDATE,
            "managerDashboard": role == WEBAPP_ROLE_HIRING_MANAGER,
            "adminDashboard": False,
            "candidateCvChallenge": role == WEBAPP_ROLE_CANDIDATE,
        }

    def _require_role(self, session_context: WebAppSessionContext, allowed_roles: set) -> None:
        if session_context.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    def _require_session_user_id(self, session_context: WebAppSessionContext):
        if not session_context.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        return UUID(session_context.user_id)

    def _require_candidate_profile(self, session_context: WebAppSessionContext):
        user_id = self._require_session_user_id(session_context)
        profile = self.candidate_profiles.get_active_by_user_id(user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")
        return profile

    def _require_vacancy(self, vacancy_id: str):
        vacancy = self.vacancies.get_by_id(UUID(vacancy_id))
        if vacancy is None or getattr(vacancy, "deleted_at", None) is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found.")
        return vacancy

    def _require_owned_vacancy(self, session_context: WebAppSessionContext, vacancy_id: str):
        vacancy = self._require_vacancy(vacancy_id)
        self._assert_manager_owns_vacancy(session_context, vacancy)
        return vacancy

    def _assert_manager_owns_vacancy(self, session_context: WebAppSessionContext, vacancy) -> None:
        user_id = self._require_session_user_id(session_context)
        if str(vacancy.manager_user_id) != str(user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    def _require_match(self, match_id: str):
        match = self.matches.get_by_id(UUID(match_id))
        if match is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
        return match

    def _serialize_candidate_profile(self, profile, current_version) -> Dict[str, Any]:
        summary = candidate_summary_snapshot(getattr(current_version, "summary_json", None))
        return {
            "id": str(profile.id),
            "state": getattr(profile, "state", None),
            "headline": summary.get("headline"),
            "targetRole": summary.get("targetRole") or getattr(profile, "target_role", None),
            "location": getattr(profile, "location_text", None),
            "countryCode": getattr(profile, "country_code", None),
            "city": getattr(profile, "city", None),
            "workFormat": getattr(profile, "work_format", None),
            "englishLevel": display_english_level(getattr(profile, "english_level", None)),
            "preferredDomains": display_domains(getattr(profile, "preferred_domains_json", None)),
            "showTakeHomeTaskRoles": getattr(profile, "show_take_home_task_roles", None),
            "showLiveCodingRoles": getattr(profile, "show_live_coding_roles", None),
            "salaryExpectation": format_money_range(
                getattr(profile, "salary_min", None),
                getattr(profile, "salary_max", None),
                getattr(profile, "salary_currency", None),
                getattr(profile, "salary_period", None),
            ),
            "summary": summary,
            "fullHardSkills": display_skill_list(candidate_version_full_hard_skills(current_version)),
            "readyAt": isoformat_or_none(getattr(profile, "ready_at", None)),
            "updatedAt": isoformat_or_none(getattr(profile, "updated_at", None)),
        }

    def _serialize_candidate_profile_detail(
        self,
        profile,
        current_version,
        *,
        candidate_user=None,
        include_identity: bool = False,
    ) -> Dict[str, Any]:
        summary = candidate_summary_snapshot(getattr(current_version, "summary_json", None))
        response = {
            **self._serialize_candidate_profile(profile, current_version),
            "profileId": str(profile.id),
            "city": getattr(profile, "city", None),
            "source": source_text_snapshot(current_version),
            "answers": {
                "salaryExpectation": format_money_range(
                    profile.salary_min,
                    profile.salary_max,
                    profile.salary_currency,
                    profile.salary_period,
                ),
                "location": getattr(profile, "location_text", None),
                "countryCode": getattr(profile, "country_code", None),
                "city": getattr(profile, "city", None),
                "workFormat": getattr(profile, "work_format", None),
                "englishLevel": display_english_level(getattr(profile, "english_level", None)),
                "preferredDomains": display_domains(getattr(profile, "preferred_domains_json", None)),
                "showTakeHomeTaskRoles": getattr(profile, "show_take_home_task_roles", None),
                "showLiveCodingRoles": getattr(profile, "show_live_coding_roles", None),
            },
            "summary": summary,
        }
        if include_identity:
            response["name"] = self._display_name(candidate_user, "Candidate")
        return response

    def _serialize_candidate_opportunity_card(self, match) -> Dict[str, Any]:
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        return {
            "id": str(match.id),
            "vacancyId": str(match.vacancy_id),
            "roleTitle": getattr(vacancy, "role_title", None),
            "budget": format_money_range(
                getattr(vacancy, "budget_min", None),
                getattr(vacancy, "budget_max", None),
                getattr(vacancy, "budget_currency", None),
                getattr(vacancy, "budget_period", None),
            ),
            "workFormat": getattr(vacancy, "work_format", None),
            "stage": match.status,
            "stageLabel": match_status_label(match.status, perspective="candidate"),
            "stageDescription": match_status_description(match.status, perspective="candidate"),
            "needsAction": match_requires_action(match.status, perspective="candidate"),
            "updatedAt": isoformat_or_none(match.updated_at),
        }

    def _serialize_vacancy_card(self, vacancy, include_manager: bool = False) -> Dict[str, Any]:
        matches = self.matches.list_all_for_vacancy(vacancy.id)
        data = {
            "id": str(vacancy.id),
            "roleTitle": vacancy.role_title,
            "state": vacancy.state,
            "budget": format_money_range(
                vacancy.budget_min,
                vacancy.budget_max,
                vacancy.budget_currency,
                vacancy.budget_period,
            ),
            "candidateCount": len(matches),
            "activePipelineCount": len([match for match in matches if match.status in self.matches.ACTIVE_MATCH_STATUSES]),
            "needsReviewCount": len(
                [match for match in matches if match_requires_action(match.status, perspective="manager")]
            ),
            "interviewCount": len(
                [match for match in matches if match.status in self.INTERVIEW_RELATED_MATCH_STATUSES]
            ),
            "connectedCount": len([match for match in matches if getattr(match, "status", None) == "approved"]),
            "updatedAt": isoformat_or_none(vacancy.updated_at),
        }
        if include_manager:
            manager_user = self.users.get_by_id(vacancy.manager_user_id)
            data["managerName"] = self._display_name(manager_user, None)
        return data

    def _serialize_vacancy_detail(self, vacancy, include_manager: bool = False) -> Dict[str, Any]:
        version = self.vacancies.get_current_version(vacancy)
        summary = vacancy_summary_snapshot(getattr(version, "summary_json", None))
        response = {
            "vacancy": {
                "id": str(vacancy.id),
                "roleTitle": vacancy.role_title,
                "state": vacancy.state,
                "seniority": vacancy.seniority_normalized,
                "budget": format_money_range(
                    vacancy.budget_min,
                    vacancy.budget_max,
                    vacancy.budget_currency,
                    vacancy.budget_period,
                ),
                "countriesAllowed": list(vacancy.countries_allowed_json or []),
                "workFormat": vacancy.work_format,
                "officeCity": getattr(vacancy, "office_city", None),
                "requiredEnglishLevel": display_english_level(getattr(vacancy, "required_english_level", None)),
                "hiringStages": display_hiring_stages(getattr(vacancy, "hiring_stages_json", None)),
                "hasTakeHomeTask": getattr(vacancy, "has_take_home_task", None),
                "takeHomePaid": getattr(vacancy, "take_home_paid", None),
                "hasLiveCoding": getattr(vacancy, "has_live_coding", None),
                "teamSize": vacancy.team_size,
                "projectDescription": vacancy.project_description,
                "primaryTechStack": list(vacancy.primary_tech_stack_json or []),
                "summary": summary,
                "source": source_text_snapshot(version),
                "openedAt": isoformat_or_none(vacancy.opened_at),
                "updatedAt": isoformat_or_none(vacancy.updated_at),
            },
            "stats": self._serialize_vacancy_card(vacancy, include_manager=include_manager),
        }
        if include_manager:
            manager_user = self.users.get_by_id(vacancy.manager_user_id)
            response["vacancy"]["managerName"] = self._display_name(manager_user, None)
        return response

    def _serialize_manager_match_card(self, match) -> Dict[str, Any]:
        profile = self.candidate_profiles.get_by_id(match.candidate_profile_id)
        candidate_user = self.users.get_by_id(profile.user_id) if profile is not None else None
        candidate_version = self.candidate_profiles.get_current_version(profile) if profile is not None else None
        return {
            "id": str(match.id),
            "candidateProfileId": str(match.candidate_profile_id),
            "candidateName": self._display_name(candidate_user, "Candidate"),
            "location": getattr(profile, "location_text", None),
            "salaryExpectation": format_money_range(
                getattr(profile, "salary_min", None),
                getattr(profile, "salary_max", None),
                getattr(profile, "salary_currency", None),
                getattr(profile, "salary_period", None),
            ),
            "workFormat": getattr(profile, "work_format", None),
            "stage": match.status,
            "stageLabel": match_status_label(match.status, perspective="manager"),
            "stageDescription": match_status_description(match.status, perspective="manager"),
            "needsAction": match_requires_action(match.status, perspective="manager"),
            "summary": candidate_summary_snapshot(getattr(candidate_version, "summary_json", None)),
            "updatedAt": isoformat_or_none(match.updated_at),
        }

    def _serialize_match_detail(self, match, *, session_context: WebAppSessionContext) -> Dict[str, Any]:
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        vacancy_version = self.vacancies.get_current_version(vacancy) if vacancy is not None else None
        candidate_profile = self.candidate_profiles.get_by_id(match.candidate_profile_id)
        candidate_version = (
            self.candidate_profiles.get_current_version(candidate_profile)
            if candidate_profile is not None
            else None
        )
        candidate_user = self.users.get_by_id(candidate_profile.user_id) if candidate_profile is not None else None
        manager_user = self.users.get_by_id(vacancy.manager_user_id) if vacancy is not None else None
        interview = self.interviews.get_session_by_match_id(match.id)
        evaluation = self.evaluations.get_by_match_id(match.id)
        vacancy_summary = vacancy_summary_snapshot(getattr(vacancy_version, "summary_json", None))
        candidate_summary = candidate_summary_snapshot(getattr(candidate_version, "summary_json", None))

        return {
            "match": {
                "id": str(match.id),
                "status": match.status,
                "statusLabel": match_status_label(
                    match.status,
                    perspective=(
                        "candidate"
                        if session_context.role == WEBAPP_ROLE_CANDIDATE
                        else "manager" if session_context.role == WEBAPP_ROLE_HIRING_MANAGER else "generic"
                    ),
                ),
                "statusDescription": match_status_description(
                    match.status,
                    perspective=(
                        "candidate"
                        if session_context.role == WEBAPP_ROLE_CANDIDATE
                        else "manager" if session_context.role == WEBAPP_ROLE_HIRING_MANAGER else "generic"
                    ),
                ),
                "needsCandidateAction": match_requires_action(match.status, perspective="candidate"),
                "needsManagerAction": match_requires_action(match.status, perspective="manager"),
                "updatedAt": isoformat_or_none(match.updated_at),
                "invitationSentAt": isoformat_or_none(match.invitation_sent_at),
                "candidateRespondedAt": isoformat_or_none(match.candidate_response_at),
                "managerDecisionAt": isoformat_or_none(match.manager_decision_at),
            },
            "vacancy": {
                "id": str(vacancy.id) if vacancy is not None else None,
                "roleTitle": getattr(vacancy, "role_title", None),
                "state": getattr(vacancy, "state", None),
                "budget": format_money_range(
                    getattr(vacancy, "budget_min", None),
                    getattr(vacancy, "budget_max", None),
                    getattr(vacancy, "budget_currency", None),
                    getattr(vacancy, "budget_period", None),
                ),
                "countriesAllowed": list(getattr(vacancy, "countries_allowed_json", None) or []),
                "workFormat": getattr(vacancy, "work_format", None),
                "officeCity": getattr(vacancy, "office_city", None),
                "requiredEnglishLevel": display_english_level(getattr(vacancy, "required_english_level", None)),
                "hiringStages": display_hiring_stages(getattr(vacancy, "hiring_stages_json", None)),
                "hasTakeHomeTask": getattr(vacancy, "has_take_home_task", None),
                "takeHomePaid": getattr(vacancy, "take_home_paid", None),
                "hasLiveCoding": getattr(vacancy, "has_live_coding", None),
                "teamSize": getattr(vacancy, "team_size", None),
                "projectDescription": getattr(vacancy, "project_description", None),
                "primaryTechStack": list(getattr(vacancy, "primary_tech_stack_json", None) or []),
                "summary": vacancy_summary,
                "whyThisRole": self._build_candidate_match_reason(
                    vacancy=vacancy,
                    candidate_profile=candidate_profile,
                    candidate_summary=candidate_summary,
                    vacancy_summary=vacancy_summary,
                ),
                "source": source_text_snapshot(vacancy_version),
                "managerName": self._display_name(manager_user, None),
            },
            "candidate": (
                self._serialize_candidate_profile_detail(
                    candidate_profile,
                    candidate_version,
                    candidate_user=candidate_user,
                    include_identity=True,
                )
                if candidate_profile is not None
                else {
                    "profileId": None,
                    "name": self._display_name(candidate_user, "Candidate"),
                    "location": None,
                    "countryCode": None,
                    "city": None,
                    "workFormat": None,
                    "salaryExpectation": None,
                    "source": source_text_snapshot(candidate_version),
                    "answers": {
                        "salaryExpectation": None,
                        "location": None,
                        "countryCode": None,
                        "city": None,
                        "workFormat": None,
                        "englishLevel": None,
                        "preferredDomains": [],
                        "showTakeHomeTaskRoles": None,
                        "showLiveCodingRoles": None,
                    },
                    "summary": candidate_summary,
                    "fullHardSkills": display_skill_list(candidate_version_full_hard_skills(candidate_version)),
                }
            ),
            "interview": {
                "sessionId": str(interview.id) if interview is not None else None,
                "state": getattr(interview, "state", None),
                "stateLabel": interview_state_label(getattr(interview, "state", None)),
                "invitedAt": isoformat_or_none(getattr(interview, "invited_at", None)),
                "acceptedAt": isoformat_or_none(getattr(interview, "accepted_at", None)),
                "startedAt": isoformat_or_none(getattr(interview, "started_at", None)),
                "completedAt": isoformat_or_none(getattr(interview, "completed_at", None)),
            },
            "evaluation": evaluation_snapshot(evaluation),
        }

    @staticmethod
    def _normalize_skill_token(value: Any) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    def _build_candidate_match_reason(
        self,
        *,
        vacancy,
        candidate_profile,
        candidate_summary: Optional[Dict[str, Any]],
        vacancy_summary: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        candidate_summary = candidate_summary or {}
        vacancy_summary = vacancy_summary or {}

        candidate_skill_map = {
            self._normalize_skill_token(skill): skill
            for skill in candidate_summary.get("skills") or []
            if self._normalize_skill_token(skill)
        }
        overlapping_skills = [
            skill
            for skill in vacancy_summary.get("skills") or []
            if self._normalize_skill_token(skill) in candidate_skill_map
        ]

        reasons: List[str] = []
        if overlapping_skills:
            rendered_skills = ", ".join(overlapping_skills[:3])
            reasons.append(f"Your profile overlaps with this role on {rendered_skills}.")
        else:
            target_role = candidate_summary.get("targetRole")
            role_title = getattr(vacancy, "role_title", None)
            if target_role and role_title:
                reasons.append(f"This role lines up well with your target profile for {target_role}.")
            elif role_title:
                reasons.append(f"This role is relevant to your current profile for {role_title}.")

        candidate_work_format = getattr(candidate_profile, "work_format", None)
        vacancy_work_format = getattr(vacancy, "work_format", None)
        if candidate_work_format and vacancy_work_format and str(candidate_work_format).lower() == str(vacancy_work_format).lower():
            reasons.append(f"It also matches your preferred work format: {candidate_work_format}.")

        candidate_country = getattr(candidate_profile, "country_code", None)
        countries_allowed = list(getattr(vacancy, "countries_allowed_json", None) or [])
        if candidate_country and countries_allowed and candidate_country in countries_allowed:
            reasons.append("Your location is already allowed for this role.")

        if reasons:
            return " ".join(reasons[:2])

        summary_text = vacancy_summary.get("approvalSummaryText") or vacancy_summary.get("headline")
        if summary_text:
            return summary_text
        return None
