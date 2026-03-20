from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import bindparam, select, text

from src.admin.session import AdminSessionContext
from src.candidate_profile.work_formats import display_work_formats
from src.db.models.candidates import CandidateProfile, CandidateProfileVersion
from src.db.models.core import Notification, RawMessage, User
from src.db.models.evaluations import IntroductionEvent
from src.db.models.matching import Match, MatchingRun
from src.db.models.vacancies import Vacancy, VacancyVersion
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.users import UsersRepository
from src.shared.hiring_taxonomy import display_domains, display_english_level, display_hiring_stages
from src.webapp.presenters import (
    candidate_summary_snapshot,
    format_money_range,
    match_status_description,
    match_status_label,
    vacancy_summary_snapshot,
)
from src.webapp.service import WebAppService


class _ResolvedUserData:
    user: User
    candidate_profile: CandidateProfile | None
    candidate_version: CandidateProfileVersion | None
    vacancies: list[Vacancy]

    def __init__(self, *, user, candidate_profile, candidate_version, vacancies):
        self.user = user
        self.candidate_profile = candidate_profile
        self.candidate_version = candidate_version
        self.vacancies = vacancies


class AdminService:
    def __init__(self, session):
        self.session = session
        self.users = UsersRepository(session)
        self.notifications = NotificationsRepository(session)

    @staticmethod
    def _require_admin(session_context: AdminSessionContext) -> None:
        if session_context.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    @staticmethod
    def _coerce_uuid(value: str | UUID) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    @staticmethod
    def _match_admin_url(match_id: UUID | str, *, app_base_url: str) -> str:
        return f"{app_base_url.rstrip('/')}/admin#/matches/{match_id}"

    @staticmethod
    def _serialize_decimal(value: Any) -> Any:
        if isinstance(value, Decimal):
            if value == value.to_integral():
                return int(value)
            return float(value)
        if isinstance(value, list):
            return [AdminService._serialize_decimal(item) for item in value]
        if isinstance(value, dict):
            return {str(key): AdminService._serialize_decimal(item) for key, item in value.items()}
        return value

    @staticmethod
    def _compact_text(value: Any, *, limit: int = 220) -> str | None:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return None
        if len(text) <= limit:
            return text
        shortened = text[: limit - 3].rstrip()
        if " " in shortened:
            shortened = shortened.rsplit(" ", 1)[0]
        return f"{shortened}..."

    def build_session_payload(self, session_context: AdminSessionContext) -> dict[str, Any]:
        self._require_admin(session_context)
        return {
            "session": session_context.to_public_dict(),
            "capabilities": {
                "adminDashboard": True,
                "userManagement": True,
                "matchManagement": True,
                "systemAnalytics": True,
                "botMessaging": True,
            },
        }

    def _load_user_related_data(self, *, include_deleted: bool = True) -> dict[UUID, _ResolvedUserData]:
        user_stmt = select(User)
        if not include_deleted:
            user_stmt = user_stmt.where(User.deleted_at.is_(None))
        users = list(self.session.execute(user_stmt.order_by(User.updated_at.desc(), User.created_at.desc())).scalars().all())
        user_ids = [user.id for user in users]

        candidate_profiles = (
            list(
                self.session.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id.in_(user_ids or [None]))
                ).scalars().all()
            )
            if user_ids
            else []
        )
        candidate_by_user_id = {profile.user_id: profile for profile in candidate_profiles}
        current_version_ids = [profile.current_version_id for profile in candidate_profiles if profile.current_version_id]
        candidate_versions = (
            list(
                self.session.execute(
                    select(CandidateProfileVersion).where(CandidateProfileVersion.id.in_(current_version_ids or [None]))
                ).scalars().all()
            )
            if current_version_ids
            else []
        )
        candidate_versions_by_id = {version.id: version for version in candidate_versions}

        vacancies = (
            list(
                self.session.execute(
                    select(Vacancy).where(Vacancy.manager_user_id.in_(user_ids or [None]))
                ).scalars().all()
            )
            if user_ids
            else []
        )
        vacancies_by_manager_id: dict[UUID, list[Vacancy]] = defaultdict(list)
        for vacancy in vacancies:
            vacancies_by_manager_id[vacancy.manager_user_id].append(vacancy)

        resolved: dict[UUID, _ResolvedUserData] = {}
        for user in users:
            candidate_profile = candidate_by_user_id.get(user.id)
            candidate_version = (
                candidate_versions_by_id.get(candidate_profile.current_version_id)
                if candidate_profile is not None and candidate_profile.current_version_id is not None
                else None
            )
            resolved[user.id] = _ResolvedUserData(
                user=user,
                candidate_profile=candidate_profile,
                candidate_version=candidate_version,
                vacancies=vacancies_by_manager_id.get(user.id, []),
            )
        return resolved

    @staticmethod
    def _user_role_bucket(data: _ResolvedUserData) -> str:
        candidate_present = bool(data.candidate_profile and getattr(data.candidate_profile, "deleted_at", None) is None)
        manager_present = any(getattr(vacancy, "deleted_at", None) is None for vacancy in data.vacancies)
        if candidate_present and manager_present:
            return "dual"
        if candidate_present or getattr(data.user, "is_candidate", False):
            return "candidate"
        if manager_present or getattr(data.user, "is_hiring_manager", False):
            return "hiring_manager"
        return "unknown"

    @staticmethod
    def _user_status_bucket(data: _ResolvedUserData) -> str:
        if getattr(data.user, "is_blocked", False):
            return "blocked"
        if getattr(data.user, "deleted_at", None) is not None:
            return "deleted_like"
        if data.candidate_profile is not None and getattr(data.candidate_profile, "deleted_at", None) is not None:
            return "deleted_like"
        non_deleted_vacancies = [vacancy for vacancy in data.vacancies if getattr(vacancy, "deleted_at", None) is None]
        if data.vacancies and not non_deleted_vacancies:
            return "deleted_like"
        return "active"

    @staticmethod
    def _user_search_blob(data: _ResolvedUserData) -> str:
        parts = [
            getattr(data.user, "display_name", None),
            getattr(data.user, "username", None),
            getattr(data.user, "telegram_user_id", None),
            getattr(data.user, "telegram_chat_id", None),
        ]
        if data.candidate_profile is not None:
            parts.extend(
                [
                    getattr(data.candidate_profile, "target_role", None),
                    getattr(data.candidate_profile, "location_text", None),
                    getattr(data.candidate_profile, "city", None),
                ]
            )
        for vacancy in data.vacancies[:5]:
            parts.extend([getattr(vacancy, "role_title", None), getattr(vacancy, "project_description", None)])
        return " ".join(str(part).lower() for part in parts if part)

    def _serialize_user_row(self, data: _ResolvedUserData) -> dict[str, Any]:
        candidate = data.candidate_profile
        candidate_version = data.candidate_version
        active_vacancies = [vacancy for vacancy in data.vacancies if getattr(vacancy, "deleted_at", None) is None]
        vacancy_states = sorted({str(getattr(vacancy, "state", "") or "") for vacancy in active_vacancies if getattr(vacancy, "state", None)})
        candidate_name = (
            WebAppService._candidate_display_name(data.user, candidate_version, getattr(data.user, "display_name", None))
            if candidate is not None
            else None
        )
        return {
            "id": str(data.user.id),
            "telegramUserId": data.user.telegram_user_id,
            "telegramChatId": data.user.telegram_chat_id,
            "displayName": data.user.display_name,
            "username": data.user.username,
            "candidateName": candidate_name,
            "role": self._user_role_bucket(data),
            "status": self._user_status_bucket(data),
            "isBlocked": bool(getattr(data.user, "is_blocked", False)),
            "blockedAt": getattr(data.user, "blocked_at", None).isoformat() if getattr(data.user, "blocked_at", None) else None,
            "blockedReason": getattr(data.user, "blocked_reason", None),
            "candidateState": getattr(candidate, "state", None) if candidate is not None else None,
            "candidateProfileId": str(candidate.id) if candidate is not None else None,
            "vacancyCount": len(active_vacancies),
            "vacancyStates": vacancy_states,
            "updatedAt": getattr(data.user, "updated_at", None).isoformat() if getattr(data.user, "updated_at", None) else None,
        }

    def list_users(
        self,
        session_context: AdminSessionContext,
        *,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
        candidate_state: Optional[str] = None,
        vacancy_state: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        self._require_admin(session_context)
        resolved = self._load_user_related_data()
        items = []
        normalized_search = " ".join(str(search or "").lower().split())
        for data in resolved.values():
            row = self._serialize_user_row(data)
            if role and row["role"] != role:
                continue
            if status_filter and row["status"] != status_filter:
                continue
            if candidate_state and row.get("candidateState") != candidate_state:
                continue
            if vacancy_state and vacancy_state not in (row.get("vacancyStates") or []):
                continue
            if normalized_search and normalized_search not in self._user_search_blob(data):
                continue
            items.append(row)

        candidate_states = Counter(item["candidateState"] for item in items if item.get("candidateState"))
        vacancy_states = Counter(state for item in items for state in (item.get("vacancyStates") or []))
        return {
            "items": sorted(items, key=lambda item: (item.get("updatedAt") or "", item["telegramUserId"]), reverse=True),
            "filters": {
                "roleOptions": ["candidate", "hiring_manager", "dual", "unknown"],
                "statusOptions": ["active", "blocked", "deleted_like"],
                "candidateStateOptions": sorted(candidate_states.keys()),
                "vacancyStateOptions": sorted(vacancy_states.keys()),
            },
            "counts": {
                "total": len(items),
                "blocked": len([item for item in items if item["isBlocked"]]),
            },
        }

    def get_user_detail(self, session_context: AdminSessionContext, *, user_id: str) -> dict[str, Any]:
        self._require_admin(session_context)
        resolved = self._load_user_related_data()
        data = resolved.get(self._coerce_uuid(user_id))
        if data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        candidate = data.candidate_profile
        candidate_version = data.candidate_version
        active_vacancies = [vacancy for vacancy in data.vacancies if getattr(vacancy, "deleted_at", None) is None]
        match_stmt = select(Match).where(
            (Match.candidate_profile_id == getattr(candidate, "id", None))
            | (Match.vacancy_id.in_([vacancy.id for vacancy in active_vacancies] or [None]))
        )
        matches = list(self.session.execute(match_stmt).scalars().all())
        return {
            "user": self._serialize_user_row(data),
            "candidate": (
                {
                    "profileId": str(candidate.id),
                    "state": getattr(candidate, "state", None),
                    "location": getattr(candidate, "location_text", None),
                    "city": getattr(candidate, "city", None),
                    "countryCode": getattr(candidate, "country_code", None),
                    "workFormat": display_work_formats(candidate),
                    "englishLevel": display_english_level(getattr(candidate, "english_level", None)),
                    "preferredDomains": display_domains(getattr(candidate, "preferred_domains_json", None)),
                    "salaryExpectation": format_money_range(
                        getattr(candidate, "salary_min", None),
                        getattr(candidate, "salary_max", None),
                        getattr(candidate, "salary_currency", None),
                        getattr(candidate, "salary_period", None),
                    ),
                    "summary": candidate_summary_snapshot(getattr(candidate_version, "summary_json", None)),
                }
                if candidate is not None
                else None
            ),
            "vacancies": [
                {
                    "id": str(vacancy.id),
                    "roleTitle": getattr(vacancy, "role_title", None),
                    "state": getattr(vacancy, "state", None),
                    "budget": format_money_range(
                        getattr(vacancy, "budget_min", None),
                        getattr(vacancy, "budget_max", None),
                        getattr(vacancy, "budget_currency", None),
                        getattr(vacancy, "budget_period", None),
                    ),
                    "workFormat": getattr(vacancy, "work_format", None),
                    "officeCity": getattr(vacancy, "office_city", None),
                    "updatedAt": getattr(vacancy, "updated_at", None).isoformat() if getattr(vacancy, "updated_at", None) else None,
                }
                for vacancy in active_vacancies
            ],
            "stats": {
                "matchCount": len(matches),
                "notificationCount": self._count_rows(Notification, Notification.user_id == data.user.id),
                "rawMessageCount": self._count_rows(RawMessage, RawMessage.user_id == data.user.id),
            },
        }

    def block_users(
        self,
        session_context: AdminSessionContext,
        *,
        user_ids: list[str],
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        self._require_admin(session_context)
        resolved_users = self._resolve_users_for_ids(user_ids)
        updated = []
        cancelled_notifications = 0
        for user in resolved_users:
            if getattr(user, "is_blocked", False):
                updated.append(str(user.id))
                continue
            self.users.set_blocked(user, blocked=True, reason=reason)
            cancelled_notifications += self._cancel_pending_notifications_for_user(user.id)
            updated.append(str(user.id))
        return {
            "status": "ok",
            "updatedUserIds": updated,
            "cancelledNotifications": cancelled_notifications,
        }

    def unblock_users(
        self,
        session_context: AdminSessionContext,
        *,
        user_ids: list[str],
    ) -> dict[str, Any]:
        self._require_admin(session_context)
        resolved_users = self._resolve_users_for_ids(user_ids)
        updated = []
        for user in resolved_users:
            if not getattr(user, "is_blocked", False):
                updated.append(str(user.id))
                continue
            self.users.set_blocked(user, blocked=False)
            updated.append(str(user.id))
        return {
            "status": "ok",
            "updatedUserIds": updated,
        }

    def preview_message(
        self,
        session_context: AdminSessionContext,
        *,
        user_ids: list[str],
        message_text: str,
    ) -> dict[str, Any]:
        self._require_admin(session_context)
        message = " ".join(str(message_text or "").split()).strip()
        if not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text is required.")
        users = self._resolve_users_for_ids(user_ids)
        deliverable = []
        skipped = []
        for user in users:
            if getattr(user, "is_blocked", False):
                skipped.append({"userId": str(user.id), "reason": "blocked"})
                continue
            if not getattr(user, "telegram_chat_id", None):
                skipped.append({"userId": str(user.id), "reason": "no_telegram_chat"})
                continue
            deliverable.append(
                {
                    "userId": str(user.id),
                    "telegramUserId": getattr(user, "telegram_user_id", None),
                    "displayName": getattr(user, "display_name", None),
                    "username": getattr(user, "username", None),
                    "telegramChatId": getattr(user, "telegram_chat_id", None),
                }
            )
        return {
            "message": {"text": message},
            "deliverable": deliverable,
            "skipped": skipped,
            "counts": {
                "selected": len(users),
                "deliverable": len(deliverable),
                "skipped": len(skipped),
            },
        }

    def send_message(
        self,
        session_context: AdminSessionContext,
        *,
        user_ids: list[str],
        message_text: str,
    ) -> dict[str, Any]:
        preview = self.preview_message(
            session_context,
            user_ids=user_ids,
            message_text=message_text,
        )
        created = []
        for row in preview["deliverable"]:
            notification = self.notifications.create(
                user_id=self._coerce_uuid(row["userId"]),
                entity_type="user",
                entity_id=self._coerce_uuid(row["userId"]),
                template_key="admin_direct_message",
                payload_json={"text": preview["message"]["text"]},
                allow_duplicate=True,
            )
            created.append(str(notification.id))
        return {
            "status": "ok",
            "notificationIds": created,
            "counts": preview["counts"],
            "skipped": preview["skipped"],
        }

    def list_matches(
        self,
        session_context: AdminSessionContext,
        *,
        status_filter: Optional[str] = None,
        fit_band: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        self._require_admin(session_context)
        matches = list(self.session.execute(select(Match).order_by(Match.updated_at.desc(), Match.created_at.desc())).scalars().all())
        payload = self._serialize_matches(matches)
        normalized_search = " ".join(str(search or "").lower().split())
        if status_filter:
            payload = [row for row in payload if row.get("status") == status_filter]
        if fit_band:
            payload = [row for row in payload if row.get("fitBand") == fit_band]
        if normalized_search:
            payload = [
                row
                for row in payload
                if normalized_search in " ".join(
                    str(value).lower()
                    for value in (
                        row.get("roleTitle"),
                        row.get("candidateName"),
                        row.get("managerName"),
                        row.get("status"),
                        row.get("id"),
                    )
                    if value
                )
            ]
        return {
            "items": payload,
            "filters": {
                "statusOptions": sorted({row["status"] for row in payload if row.get("status")}),
                "fitBandOptions": sorted({row["fitBand"] for row in payload if row.get("fitBand")}),
            },
            "counts": {"total": len(payload)},
        }

    def get_match_detail(self, session_context: AdminSessionContext, *, match_id: str) -> dict[str, Any]:
        self._require_admin(session_context)
        match = self.session.execute(select(Match).where(Match.id == self._coerce_uuid(match_id))).scalar_one_or_none()
        if match is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")

        serialized = self._serialize_matches([match])[0]
        vacancy = self.session.execute(select(Vacancy).where(Vacancy.id == match.vacancy_id)).scalar_one_or_none()
        vacancy_version = (
            self.session.execute(select(VacancyVersion).where(VacancyVersion.id == match.vacancy_version_id)).scalar_one_or_none()
            if match.vacancy_version_id
            else None
        )
        candidate = self.session.execute(select(CandidateProfile).where(CandidateProfile.id == match.candidate_profile_id)).scalar_one_or_none()
        candidate_version = (
            self.session.execute(select(CandidateProfileVersion).where(CandidateProfileVersion.id == match.candidate_profile_version_id)).scalar_one_or_none()
            if match.candidate_profile_version_id
            else None
        )
        intro = self.session.execute(select(IntroductionEvent).where(IntroductionEvent.match_id == match.id)).scalar_one_or_none()
        run = self.session.execute(select(MatchingRun).where(MatchingRun.id == match.matching_run_id)).scalar_one_or_none()
        candidate_user = self.users.get_by_id(candidate.user_id) if candidate is not None else None
        manager_user = self.users.get_by_id(vacancy.manager_user_id) if vacancy is not None else None
        return {
            "match": serialized,
            "vacancy": (
                {
                    "id": str(vacancy.id),
                    "roleTitle": getattr(vacancy, "role_title", None),
                    "state": getattr(vacancy, "state", None),
                    "budget": format_money_range(
                        getattr(vacancy, "budget_min", None),
                        getattr(vacancy, "budget_max", None),
                        getattr(vacancy, "budget_currency", None),
                        getattr(vacancy, "budget_period", None),
                    ),
                    "workFormat": getattr(vacancy, "work_format", None),
                    "officeCity": getattr(vacancy, "office_city", None),
                    "countriesAllowed": list(getattr(vacancy, "countries_allowed_json", None) or []),
                    "requiredEnglishLevel": display_english_level(getattr(vacancy, "required_english_level", None)),
                    "teamSize": getattr(vacancy, "team_size", None),
                    "projectDescription": getattr(vacancy, "project_description", None),
                    "primaryTechStack": list(getattr(vacancy, "primary_tech_stack_json", None) or []),
                    "hiringStages": display_hiring_stages(getattr(vacancy, "hiring_stages_json", None)),
                    "hasTakeHomeTask": getattr(vacancy, "has_take_home_task", None),
                    "takeHomePaid": getattr(vacancy, "take_home_paid", None),
                    "hasLiveCoding": getattr(vacancy, "has_live_coding", None),
                    "summary": vacancy_summary_snapshot(getattr(vacancy_version, "summary_json", None)),
                    "managerName": getattr(manager_user, "display_name", None) or getattr(manager_user, "username", None),
                }
                if vacancy is not None
                else None
            ),
            "candidate": (
                {
                    "profileId": str(candidate.id),
                    "name": WebAppService._candidate_display_name(candidate_user, candidate_version, getattr(candidate_user, "display_name", None)),
                    "state": getattr(candidate, "state", None),
                    "salaryExpectation": format_money_range(
                        getattr(candidate, "salary_min", None),
                        getattr(candidate, "salary_max", None),
                        getattr(candidate, "salary_currency", None),
                        getattr(candidate, "salary_period", None),
                    ),
                    "location": getattr(candidate, "location_text", None),
                    "city": getattr(candidate, "city", None),
                    "countryCode": getattr(candidate, "country_code", None),
                    "workFormat": display_work_formats(candidate),
                    "englishLevel": display_english_level(getattr(candidate, "english_level", None)),
                    "preferredDomains": display_domains(getattr(candidate, "preferred_domains_json", None)),
                    "showTakeHomeTaskRoles": getattr(candidate, "show_take_home_task_roles", None),
                    "showLiveCodingRoles": getattr(candidate, "show_live_coding_roles", None),
                    "summary": candidate_summary_snapshot(getattr(candidate_version, "summary_json", None)),
                }
                if candidate is not None
                else None
            ),
            "run": (
                {
                    "id": str(run.id),
                    "status": getattr(run, "status", None),
                    "triggerType": getattr(run, "trigger_type", None),
                    "candidatePoolCount": getattr(run, "candidate_pool_count", None),
                    "hardFilteredCount": getattr(run, "hard_filtered_count", None),
                    "shortlistedCount": getattr(run, "shortlisted_count", None),
                    "payload": self._serialize_decimal(getattr(run, "payload_json", None)),
                }
                if run is not None
                else None
            ),
            "introduction": (
                {
                    "id": str(intro.id),
                    "status": getattr(intro, "status", None),
                    "mode": getattr(intro, "introduction_mode", None),
                    "introducedAt": getattr(intro, "introduced_at", None).isoformat() if getattr(intro, "introduced_at", None) else None,
                }
                if intro is not None
                else None
            ),
        }

    def analytics_overview(self, session_context: AdminSessionContext) -> dict[str, Any]:
        self._require_admin(session_context)
        users = list(self.session.execute(select(User)).scalars().all())
        candidate_profiles = list(self.session.execute(select(CandidateProfile)).scalars().all())
        vacancies = list(self.session.execute(select(Vacancy)).scalars().all())
        matches = list(self.session.execute(select(Match)).scalars().all())
        matching_runs = list(self.session.execute(select(MatchingRun).order_by(MatchingRun.created_at.desc()).limit(20)).scalars().all())
        introductions = list(self.session.execute(select(IntroductionEvent)).scalars().all())

        role_counts = Counter()
        blocked_users = 0
        resolved = self._load_user_related_data()
        for data in resolved.values():
            role_counts[self._user_role_bucket(data)] += 1
            if getattr(data.user, "is_blocked", False):
                blocked_users += 1

        return {
            "users": {
                "total": len(users),
                "blocked": blocked_users,
                "byRole": dict(role_counts),
            },
            "candidates": {
                "total": len(candidate_profiles),
                "byState": dict(Counter(getattr(profile, "state", None) for profile in candidate_profiles if getattr(profile, "state", None))),
                "ready": len([profile for profile in candidate_profiles if getattr(profile, "state", None) == "READY"]),
            },
            "vacancies": {
                "total": len(vacancies),
                "byState": dict(Counter(getattr(vacancy, "state", None) for vacancy in vacancies if getattr(vacancy, "state", None))),
                "open": len([vacancy for vacancy in vacancies if getattr(vacancy, "state", None) == "OPEN"]),
            },
            "matches": {
                "total": len(matches),
                "byStatus": dict(Counter(getattr(match, "status", None) for match in matches if getattr(match, "status", None))),
                "byFitBand": dict(Counter((getattr(match, "rationale_json", None) or {}).get("fit_band") or "unknown" for match in matches)),
                "contactShares": len(introductions),
                "approvals": len([match for match in matches if getattr(match, "status", None) == "approved"]),
                "skips": len([match for match in matches if getattr(match, "status", None) in {"candidate_skipped", "manager_skipped"}]),
            },
            "recentMatchingRuns": [
                {
                    "id": str(run.id),
                    "vacancyId": str(run.vacancy_id),
                    "triggerType": getattr(run, "trigger_type", None),
                    "status": getattr(run, "status", None),
                    "candidatePoolCount": getattr(run, "candidate_pool_count", None),
                    "hardFilteredCount": getattr(run, "hard_filtered_count", None),
                    "shortlistedCount": getattr(run, "shortlisted_count", None),
                    "createdAt": getattr(run, "created_at", None).isoformat() if getattr(run, "created_at", None) else None,
                }
                for run in matching_runs
            ],
            "funnel": {
                "shortlisted": len([match for match in matches if getattr(match, "status", None) == "shortlisted"]),
                "candidateDecisionPending": len([match for match in matches if getattr(match, "status", None) == "candidate_decision_pending"]),
                "candidateApplied": len([match for match in matches if getattr(match, "status", None) == "candidate_applied"]),
                "managerDecisionPending": len([match for match in matches if getattr(match, "status", None) == "manager_decision_pending"]),
                "managerApprovedAwaitingCandidate": len([match for match in matches if getattr(match, "status", None) == "manager_interview_requested"]),
                "approved": len([match for match in matches if getattr(match, "status", None) == "approved"]),
                "skippedOrExpired": len([match for match in matches if getattr(match, "status", None) in {"candidate_skipped", "manager_skipped", "expired"}]),
            },
        }

    def _serialize_matches(self, matches: list[Match]) -> list[dict[str, Any]]:
        if not matches:
            return []
        vacancy_ids = {match.vacancy_id for match in matches}
        candidate_ids = {match.candidate_profile_id for match in matches}
        candidate_version_ids = {match.candidate_profile_version_id for match in matches if match.candidate_profile_version_id}

        vacancies = {
            vacancy.id: vacancy
            for vacancy in self.session.execute(select(Vacancy).where(Vacancy.id.in_(list(vacancy_ids)))).scalars().all()
        }
        candidates = {
            profile.id: profile
            for profile in self.session.execute(select(CandidateProfile).where(CandidateProfile.id.in_(list(candidate_ids)))).scalars().all()
        }
        versions = {
            version.id: version
            for version in self.session.execute(
                select(CandidateProfileVersion).where(CandidateProfileVersion.id.in_(list(candidate_version_ids or [None])))
            ).scalars().all()
        } if candidate_version_ids else {}

        manager_user_ids = {vacancy.manager_user_id for vacancy in vacancies.values() if getattr(vacancy, "manager_user_id", None)}
        candidate_user_ids = {candidate.user_id for candidate in candidates.values() if getattr(candidate, "user_id", None)}
        users = {
            user.id: user
            for user in self.session.execute(
                select(User).where(User.id.in_(list(manager_user_ids | candidate_user_ids or {None})))
            ).scalars().all()
        } if (manager_user_ids or candidate_user_ids) else {}

        rows: list[dict[str, Any]] = []
        for match in matches:
            vacancy = vacancies.get(match.vacancy_id)
            candidate = candidates.get(match.candidate_profile_id)
            candidate_user = users.get(candidate.user_id) if candidate is not None else None
            manager_user = users.get(vacancy.manager_user_id) if vacancy is not None else None
            candidate_version = versions.get(match.candidate_profile_version_id) if match.candidate_profile_version_id else None
            rationale = getattr(match, "rationale_json", None) or {}
            rows.append(
                {
                    "id": str(match.id),
                    "vacancyId": str(match.vacancy_id),
                    "candidateProfileId": str(match.candidate_profile_id),
                    "matchingRunId": str(match.matching_run_id),
                    "roleTitle": getattr(vacancy, "role_title", None),
                    "candidateName": WebAppService._candidate_display_name(candidate_user, candidate_version, getattr(candidate_user, "display_name", None)),
                    "managerName": getattr(manager_user, "display_name", None) or getattr(manager_user, "username", None),
                    "status": getattr(match, "status", None),
                    "statusLabel": match_status_label(getattr(match, "status", None), perspective="generic"),
                    "statusDescription": match_status_description(getattr(match, "status", None), perspective="generic"),
                    "hardFilterPassed": getattr(match, "hard_filter_passed", None),
                    "filterReasonCodes": list(getattr(match, "filter_reason_codes_json", None) or []),
                    "fitBand": rationale.get("fit_band"),
                    "fitBandLabel": rationale.get("fit_band_label"),
                    "matchedSignals": list(rationale.get("matched_signals") or []),
                    "gapSignals": list(rationale.get("gap_signals") or []),
                    "llmRationale": self._compact_text(rationale.get("llm_rationale"), limit=260),
                    "deterministicScore": self._serialize_decimal(getattr(match, "deterministic_score", None)),
                    "llmRankScore": self._serialize_decimal(getattr(match, "llm_rank_score", None)),
                    "embeddingScore": self._serialize_decimal(getattr(match, "embedding_score", None)),
                    "updatedAt": getattr(match, "updated_at", None).isoformat() if getattr(match, "updated_at", None) else None,
                    "adminUrl": self._match_admin_url(match.id, app_base_url=self._app_base_url()),
                }
            )
        return rows

    def _resolve_users_for_ids(self, user_ids: list[str]) -> list[User]:
        normalized_ids = [self._coerce_uuid(value) for value in user_ids]
        if not normalized_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one user is required.")
        users = list(self.session.execute(select(User).where(User.id.in_(normalized_ids))).scalars().all())
        found = {user.id for user in users}
        missing = [str(user_id) for user_id in normalized_ids if user_id not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Users not found: {', '.join(missing)}",
            )
        return users

    def _cancel_pending_notifications_for_user(self, user_id: UUID) -> int:
        rows = self.notifications.list_pending_dispatchable_for_user(user_id=user_id, limit=500)
        cancelled = 0
        for row in rows:
            self.notifications.mark_cancelled(row, reason="user_blocked")
            cancelled += 1
        return cancelled

    def _count_rows(self, model, condition) -> int:
        return len(list(self.session.execute(select(model).where(condition)).scalars().all()))

    def _app_base_url(self) -> str:
        from src.config.settings import get_settings

        return get_settings().app_base_url

    def delete_user(self, session_context: AdminSessionContext, *, user_id: str) -> dict[str, Any]:
        self._require_admin(session_context)
        target_user_id = self._coerce_uuid(user_id)
        user = self.users.get_by_id(target_user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        plan = self._build_delete_plan(user_id=target_user_id)
        summary = self._delete_user_with_plan(user_id=target_user_id, plan=plan)
        return {
            "status": "ok",
            "userId": str(target_user_id),
            "deleted": summary,
        }

    def _select_ids(self, sql: str, params: dict[str, Any]) -> list[str]:
        return [str(row[0]) for row in self.session.execute(text(sql), params).all()]

    def _delete_by_ids(self, sql: str, ids: list[str]) -> int:
        if not ids:
            return 0
        stmt = text(sql).bindparams(bindparam("ids", expanding=True))
        return int(self.session.execute(stmt, {"ids": list(ids)}).rowcount or 0)

    def _delete_scalar(self, sql: str, params: dict[str, Any]) -> int:
        return int(self.session.execute(text(sql), params).rowcount or 0)

    def _build_delete_plan(self, *, user_id: UUID) -> dict[str, list[str]]:
        user_id_str = str(user_id)
        candidate_profile_ids = self._select_ids(
            "select id from candidate_profiles where user_id = :user_id",
            {"user_id": user_id_str},
        )
        vacancy_ids = self._select_ids(
            "select id from vacancies where manager_user_id = :user_id",
            {"user_id": user_id_str},
        )
        candidate_version_ids = (
            self._select_ids(
                "select id from candidate_profile_versions where profile_id = any(:profile_ids)",
                {"profile_ids": candidate_profile_ids},
            )
            if candidate_profile_ids
            else []
        )
        vacancy_version_ids = (
            self._select_ids(
                "select id from vacancy_versions where vacancy_id = any(:vacancy_ids)",
                {"vacancy_ids": vacancy_ids},
            )
            if vacancy_ids
            else []
        )
        matching_run_ids = self._select_ids(
            """
            select id
            from matching_runs
            where vacancy_id = any(:vacancy_ids)
               or trigger_candidate_profile_id = any(:candidate_profile_ids)
            """,
            {
                "vacancy_ids": vacancy_ids or [None],
                "candidate_profile_ids": candidate_profile_ids or [None],
            },
        )
        match_ids = self._select_ids(
            """
            select id
            from matches
            where candidate_profile_id = any(:candidate_profile_ids)
               or vacancy_id = any(:vacancy_ids)
               or matching_run_id = any(:matching_run_ids)
            """,
            {
                "candidate_profile_ids": candidate_profile_ids or [None],
                "vacancy_ids": vacancy_ids or [None],
                "matching_run_ids": matching_run_ids or [None],
            },
        )
        invite_wave_ids = (
            self._select_ids(
                """
                select id
                from invite_waves
                where vacancy_id = any(:vacancy_ids)
                   or matching_run_id = any(:matching_run_ids)
                """,
                {
                    "vacancy_ids": vacancy_ids or [None],
                    "matching_run_ids": matching_run_ids or [None],
                },
            )
            if vacancy_ids or matching_run_ids
            else []
        )
        interview_session_ids = self._select_ids(
            """
            select id
            from interview_sessions
            where candidate_profile_id = any(:candidate_profile_ids)
               or vacancy_id = any(:vacancy_ids)
               or match_id = any(:match_ids)
            """,
            {
                "candidate_profile_ids": candidate_profile_ids or [None],
                "vacancy_ids": vacancy_ids or [None],
                "match_ids": match_ids or [None],
            },
        )
        interview_question_ids = (
            self._select_ids(
                "select id from interview_questions where session_id = any(:session_ids)",
                {"session_ids": interview_session_ids},
            )
            if interview_session_ids
            else []
        )
        return {
            "candidate_profile_ids": candidate_profile_ids,
            "candidate_version_ids": candidate_version_ids,
            "vacancy_ids": vacancy_ids,
            "vacancy_version_ids": vacancy_version_ids,
            "matching_run_ids": matching_run_ids,
            "match_ids": match_ids,
            "invite_wave_ids": invite_wave_ids,
            "interview_session_ids": interview_session_ids,
            "interview_question_ids": interview_question_ids,
        }

    def _delete_user_with_plan(self, *, user_id: UUID, plan: dict[str, list[str]]) -> dict[str, int]:
        user_id_str = str(user_id)
        summary: dict[str, int] = {}
        summary["introduction_events"] = self._delete_scalar(
            """
            delete from introduction_events
            where candidate_user_id = :user_id
               or manager_user_id = :user_id
               or match_id = any(:match_ids)
            """,
            {"user_id": user_id_str, "match_ids": plan["match_ids"] or [None]},
        )
        summary["evaluation_results"] = self._delete_scalar(
            """
            delete from evaluation_results
            where match_id = any(:match_ids)
               or interview_session_id = any(:session_ids)
            """,
            {
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["interview_answers"] = self._delete_scalar(
            """
            delete from interview_answers
            where session_id = any(:session_ids)
               or question_id = any(:question_ids)
            """,
            {
                "session_ids": plan["interview_session_ids"] or [None],
                "question_ids": plan["interview_question_ids"] or [None],
            },
        )
        summary["interview_questions"] = self._delete_by_ids(
            "delete from interview_questions where id in :ids",
            plan["interview_question_ids"],
        )
        summary["interview_sessions"] = self._delete_by_ids(
            "delete from interview_sessions where id in :ids",
            plan["interview_session_ids"],
        )
        summary["invite_waves"] = self._delete_by_ids(
            "delete from invite_waves where id in :ids",
            plan["invite_wave_ids"],
        )
        summary["matches"] = self._delete_by_ids(
            "delete from matches where id in :ids",
            plan["match_ids"],
        )
        summary["matching_runs"] = self._delete_by_ids(
            "delete from matching_runs where id in :ids",
            plan["matching_run_ids"],
        )
        summary["candidate_cv_challenge_attempts"] = self._delete_scalar(
            "delete from candidate_cv_challenge_attempts where candidate_profile_id = any(:profile_ids)",
            {"profile_ids": plan["candidate_profile_ids"] or [None]},
        )
        summary["candidate_verifications"] = self._delete_scalar(
            "delete from candidate_verifications where profile_id = any(:profile_ids)",
            {"profile_ids": plan["candidate_profile_ids"] or [None]},
        )
        summary["candidate_profile_current_version_unlinks"] = self._delete_scalar(
            """
            update candidate_profiles
            set current_version_id = null
            where user_id = :user_id
              and current_version_id is not null
            """,
            {"user_id": user_id_str},
        )
        summary["vacancy_current_version_unlinks"] = self._delete_scalar(
            """
            update vacancies
            set current_version_id = null
            where manager_user_id = :user_id
              and current_version_id is not null
            """,
            {"user_id": user_id_str},
        )
        summary["candidate_profile_versions"] = self._delete_by_ids(
            "delete from candidate_profile_versions where id in :ids",
            plan["candidate_version_ids"],
        )
        summary["vacancy_versions"] = self._delete_by_ids(
            "delete from vacancy_versions where id in :ids",
            plan["vacancy_version_ids"],
        )
        summary["notifications"] = self._delete_scalar(
            "delete from notifications where user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["outbox_events"] = self._delete_scalar(
            """
            delete from outbox_events
            where (entity_type = 'user' and entity_id = cast(:user_id as uuid))
               or (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "user_id": user_id_str,
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["state_transition_logs"] = self._delete_scalar(
            """
            delete from state_transition_logs
            where actor_user_id = :user_id
               or (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "user_id": user_id_str,
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["job_execution_logs"] = self._delete_scalar(
            """
            delete from job_execution_logs
            where (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["user_consents"] = self._delete_scalar(
            "delete from user_consents where user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["raw_messages"] = self._delete_scalar(
            "delete from raw_messages where user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["files"] = self._delete_scalar(
            "delete from files where owner_user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["candidate_profiles"] = self._delete_scalar(
            "delete from candidate_profiles where user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["vacancies"] = self._delete_scalar(
            "delete from vacancies where manager_user_id = :user_id",
            {"user_id": user_id_str},
        )
        summary["users"] = self._delete_scalar(
            "delete from users where id = :user_id",
            {"user_id": user_id_str},
        )
        self.session.flush()
        return summary
