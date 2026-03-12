from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.users import UsersRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.evaluation.package_builder import build_candidate_package
from src.evaluation.package_builder import build_vacancy_package
from src.messaging.service import MessagingService
from src.notifications.rendering import render_notification_text
from src.state.service import StateService
from src.telegram.keyboards import (
    candidate_vacancy_inline_keyboard,
    manager_pre_interview_inline_keyboard,
)
from src.matching.policy import (
    CANDIDATE_ACTIVE_APPLICATION_STATUSES,
    MATCH_BATCH_SIZE,
    MATCH_STATUS_APPROVED,
    MATCH_STATUS_CANDIDATE_APPLIED,
    MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    MATCH_STATUS_CANDIDATE_SKIPPED,
    MATCH_STATUS_MANAGER_DECISION_PENDING,
    MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
    MATCH_STATUS_MANAGER_SKIPPED,
    MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE,
    MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY,
    VACANCY_INTERVIEW_PIPELINE_STATUSES,
    next_candidate_vacancy_batch_size,
    next_manager_review_batch_size,
)
from src.matching.scoring import FIT_BAND_PRIORITY, fit_band_label


@dataclass(frozen=True)
class ManagerPreInterviewActionResult:
    status: str


@dataclass(frozen=True)
class CandidateVacancyActionResult:
    status: str


class MatchingReviewService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.verifications = CandidateVerificationsRepository(session)
        self.evaluations = EvaluationsRepository(session)
        self.matches = MatchingRepository(session)
        self.notifications = NotificationsRepository(session)
        self.users = UsersRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    @staticmethod
    def _match_fit_band(match) -> str:
        rationale = getattr(match, "rationale_json", None) or {}
        value = str(rationale.get("fit_band") or "").strip().lower()
        if value in FIT_BAND_PRIORITY:
            return value
        return "strong"

    @staticmethod
    def _match_gap_signals(match) -> list[str]:
        rationale = getattr(match, "rationale_json", None) or {}
        result = []
        seen = set()
        for value in rationale.get("gap_signals") or []:
            cleaned = " ".join(str(value or "").split()).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
            if len(result) >= 3:
                break
        return result

    def _sort_matches_for_manager_review(self, matches: list) -> list:
        return sorted(
            matches,
            key=lambda match: (
                FIT_BAND_PRIORITY.get(self._match_fit_band(match), 99),
                getattr(match, "llm_rank_position", None) or 999,
                -(float(getattr(match, "llm_rank_score", None) or 0.0)),
                -(float(getattr(match, "deterministic_score", None) or 0.0)),
            ),
        )

    def _candidate_label(self, candidate_profile) -> str:
        candidate_user = self.users.get_by_id(candidate_profile.user_id)
        if candidate_user is None:
            return "Candidate"
        return (
            getattr(candidate_user, "display_name", None)
            or getattr(candidate_user, "username", None)
            or "Candidate"
        )

    def _render_candidate_package_message(self, *, match, vacancy, slot_no: int | None = None) -> str:
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        if candidate is None:
            if slot_no is None:
                return "Candidate data is unavailable."
            return f"{slot_no}. Candidate data is unavailable."
        candidate_user = self.users.get_by_id(candidate.user_id)
        candidate_version = self.candidates.get_version_by_id(match.candidate_profile_version_id)
        verification = self.verifications.get_latest_submitted_by_profile_id(candidate.id)
        package = build_candidate_package(
            candidate_user=candidate_user,
            candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            candidate_profile=candidate,
            vacancy=vacancy,
            evaluation={},
            verification=verification,
        )
        body = render_notification_text(
            template_key="manager_candidate_review_ready",
            payload={"candidate_package": package},
        )
        fit_band = self._match_fit_band(match)
        fit_band_text = fit_band_label(fit_band) or "Fit"
        gap_signals = self._match_gap_signals(match)
        header_lines = [f"Fit: {fit_band_text}"]
        if gap_signals:
            header_lines.append(f"Gaps: {' '.join(gap_signals[:2])}")
        body = "\n".join(header_lines + [body])
        if slot_no is None:
            return body
        return f"{slot_no}.\n{body}"

    @staticmethod
    def _vacancy_budget_label(vacancy) -> str | None:
        budget_min = getattr(vacancy, "budget_min", None)
        budget_max = getattr(vacancy, "budget_max", None)
        currency = getattr(vacancy, "budget_currency", None)
        period = getattr(vacancy, "budget_period", None)
        if budget_min is None and budget_max is None:
            return None
        if budget_min is not None and budget_max is not None:
            amount = f"{budget_min:.0f}-{budget_max:.0f}"
        else:
            amount = f"{(budget_min if budget_min is not None else budget_max):.0f}"
        if currency:
            amount = f"{amount} {currency}"
        if period:
            amount = f"{amount} / {period}"
        return amount

    @staticmethod
    def _truncate_text(value: str | None, *, limit: int = 240) -> str | None:
        if not value:
            return None
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."

    def _render_vacancy_card_message(self, *, match, slot_no: int | None = None) -> str:
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if vacancy is None:
            if slot_no is None:
                return "Vacancy data is unavailable."
            return f"{slot_no}. Vacancy data is unavailable."

        vacancy_version = self.vacancies.get_version_by_id(getattr(match, "vacancy_version_id", None))
        package = build_vacancy_package(
            vacancy=vacancy,
            vacancy_summary=(vacancy_version.summary_json or {}) if vacancy_version else {},
        )
        intro_text = None
        if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
            intro_text = self._copy(
                f"The hiring manager already approved you for {getattr(vacancy, 'role_title', None) or 'this role'}. "
                "If you still want to move forward, tap Connect and I will share contacts right away."
            )
        body = render_notification_text(
            template_key="candidate_vacancy_review_ready",
            payload={
                "text": intro_text,
                "vacancy_package": package,
            },
        )
        if slot_no is None:
            return body
        return f"{slot_no}.\n{body}"

    @staticmethod
    def _build_counterparty_payload(user) -> dict:
        if user is None:
            return {}
        payload = {
            "name": getattr(user, "display_name", None),
            "username": getattr(user, "username", None),
            "phone_number": getattr(user, "phone_number", None),
        }
        return {key: value for key, value in payload.items() if value}

    def _share_contacts(
        self,
        *,
        match,
        candidate_user,
        manager_user,
        vacancy,
        candidate_text: str,
        manager_text: str,
    ) -> None:
        self.evaluations.create_introduction_event(
            match_id=match.id,
            candidate_user_id=getattr(candidate_user, "id", None),
            manager_user_id=getattr(manager_user, "id", None),
            introduction_mode="telegram_handoff",
        )
        self.notifications.create(
            user_id=getattr(candidate_user, "id", None),
            entity_type="match",
            entity_id=match.id,
            template_key="candidate_approved_introduction",
            payload_json={
                "text": candidate_text,
                "counterparty": self._build_counterparty_payload(manager_user),
            },
        )
        self.notifications.create(
            user_id=getattr(manager_user, "id", None),
            entity_type="match",
            entity_id=match.id,
            template_key="manager_candidate_approved",
            payload_json={
                "text": manager_text,
                "counterparty": self._build_counterparty_payload(candidate_user),
            },
        )

    def _build_manager_batch_entries(self, *, vacancy, batch: list) -> list[dict]:
        role_title = getattr(vacancy, "role_title", None) or "this vacancy"
        fit_band = self._match_fit_band(batch[0]) if batch else None
        if fit_band == "medium":
            intro_text = (
                f"I found {len(batch)} medium-fit candidate matches for {role_title}. "
                "Strong-fit candidates are exhausted for now, so each card calls out the main gaps."
            )
        elif fit_band == "low":
            intro_text = (
                f"I found {len(batch)} low-fit candidate matches for {role_title}. "
                "Only review these if you want to stretch beyond the stronger options. Main gaps are called out in each card."
            )
        else:
            intro_text = (
                f"I found {len(batch)} strong-fit candidate matches for {role_title}. "
                "Review the candidate cards below and use the buttons under each profile to connect or skip."
            )
        entries = [
            {
                "text": self._copy(intro_text)
            }
        ]
        for match in batch:
            entries.append(
                {
                    "text": self._render_candidate_package_message(
                    match=match,
                    vacancy=vacancy,
                        slot_no=None,
                    ),
                    "reply_markup": manager_pre_interview_inline_keyboard(match_id=str(match.id)),
                }
            )
        return entries

    def _build_candidate_batch_entries(self, *, batch: list) -> list[dict]:
        entries = [
            {
                "text": self._copy(
                    f"I found {len(batch)} matching roles for you. "
                    "Review the vacancy cards below and use the buttons under each role to apply or skip."
                )
            }
        ]
        for match in batch:
            primary_text = "Connect" if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED else "Apply"
            entries.append(
                {
                    "text": self._render_vacancy_card_message(match=match, slot_no=None),
                    "reply_markup": candidate_vacancy_inline_keyboard(
                        match_id=str(match.id),
                        primary_text=primary_text,
                    ),
                }
            )
        return entries

    def _candidate_active_application_count(self, candidate_profile_id) -> int:
        return sum(
            1
            for match in self.matches.list_active_for_candidate(candidate_profile_id)
            if getattr(match, "status", None) in CANDIDATE_ACTIVE_APPLICATION_STATUSES
        )

    def _vacancy_active_pipeline_count(self, vacancy_id) -> int:
        return sum(
            1
            for match in self.matches.list_active_for_vacancy(vacancy_id)
            if getattr(match, "status", None) in VACANCY_INTERVIEW_PIPELINE_STATUSES
        )

    def _candidate_batch_limit(self, candidate_profile_id) -> int:
        active_count = self._candidate_active_application_count(candidate_profile_id)
        return next_candidate_vacancy_batch_size(active_count)

    def _manager_batch_limit(self, vacancy_id) -> int:
        active_count = self._vacancy_active_pipeline_count(vacancy_id)
        return next_manager_review_batch_size(active_count)

    def dispatch_manager_batch_for_vacancy(
        self,
        *,
        vacancy_id,
        force: bool = False,
        trigger_type: str = "job",
    ) -> dict:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        if vacancy is None or getattr(vacancy, "manager_user_id", None) is None:
            return {
                "status": "vacancy_not_found",
                "vacancy_id": str(vacancy_id),
                "batch_count": 0,
                "notified": False,
            }

        presentation_limit = self._manager_batch_limit(vacancy.id)
        if presentation_limit <= 0:
            if force:
                self.notifications.create(
                    user_id=vacancy.manager_user_id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"You already have {MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY} candidates "
                            "waiting on this vacancy pipeline. "
                            "Close one of the active decisions before I send more profiles."
                        ),
                    },
                    allow_duplicate=True,
                )
            return {
                "status": "vacancy_cap_reached",
                "vacancy_id": str(vacancy_id),
                "batch_count": 0,
                "promoted_count": 0,
                "notified": force,
            }

        current_batch = list(
            self.matches.list_pre_interview_review_for_vacancy(
                vacancy_id,
                limit=presentation_limit,
            )
        )
        preexisting_count = len(current_batch)
        current_batch_ids = {match.id for match in current_batch}
        newly_promoted: list = []
        promoted_count = 0
        if len(current_batch) < presentation_limit:
            shortlisted = self._sort_matches_for_manager_review(
                self.matches.list_shortlisted_for_vacancy(
                    vacancy_id,
                    limit=MATCH_BATCH_SIZE * 6,
                )
            )
            available_shortlisted = [
                match for match in shortlisted if match.id not in current_batch_ids
            ]
            if current_batch:
                target_fit_band = self._match_fit_band(self._sort_matches_for_manager_review(current_batch)[0])
            else:
                target_fit_band = self._match_fit_band(available_shortlisted[0]) if available_shortlisted else None
            for match in available_shortlisted:
                if target_fit_band and self._match_fit_band(match) != target_fit_band:
                    continue
                if match.id in current_batch_ids:
                    continue
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_MANAGER_DECISION_PENDING,
                    trigger_type=trigger_type,
                    state_field="status",
                    metadata_json={"vacancy_id": str(vacancy_id), "presentation": "manager_pre_interview_review"},
                )
                current_batch.append(match)
                current_batch_ids.add(match.id)
                newly_promoted.append(match)
                promoted_count += 1
                if len(current_batch) >= presentation_limit:
                    break

        if not current_batch:
            return {
                "status": "empty",
                "vacancy_id": str(vacancy_id),
                "batch_count": 0,
                "promoted_count": promoted_count,
                "notified": False,
            }

        if promoted_count == 0 and preexisting_count > 0:
            return {
                "status": "already_presented",
                "vacancy_id": str(vacancy_id),
                "batch_count": len(current_batch),
                "promoted_count": promoted_count,
                "notified": False,
            }

        notification_batch = current_batch if preexisting_count == 0 else newly_promoted
        self.notifications.create(
            user_id=vacancy.manager_user_id,
            entity_type="vacancy",
            entity_id=vacancy.id,
            template_key="manager_pre_interview_review_ready",
            payload_json={
                "message_entries": self._build_manager_batch_entries(vacancy=vacancy, batch=notification_batch),
            },
            allow_duplicate=True,
        )
        return {
            "status": "dispatched",
            "vacancy_id": str(vacancy_id),
            "batch_count": len(current_batch),
            "notified_count": len(notification_batch),
            "promoted_count": promoted_count,
            "fit_band": self._match_fit_band(notification_batch[0]) if notification_batch else None,
            "notified": True,
        }

    def current_batch_size_for_manager(self, *, manager_user_id) -> int:
        vacancy_ids = [vacancy.id for vacancy in self.vacancies.get_by_manager_user_id(manager_user_id)]
        latest = self.matches.get_latest_pre_interview_review_for_manager(vacancy_ids)
        if latest is None:
            return 0
        return len(self.matches.list_pre_interview_review_for_vacancy(latest.vacancy_id, limit=MATCH_BATCH_SIZE))

    def dispatch_candidate_batch_for_profile(
        self,
        *,
        candidate_profile_id,
        force: bool = False,
        trigger_type: str = "job",
    ) -> dict:
        candidate = self.candidates.get_by_id(candidate_profile_id)
        if candidate is None or getattr(candidate, "user_id", None) is None:
            return {
                "status": "candidate_not_found",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": 0,
                "notified": False,
            }

        presentation_limit = self._candidate_batch_limit(candidate.id)
        if presentation_limit <= 0:
            if force:
                self.notifications.create(
                    user_id=candidate.user_id,
                    entity_type="candidate_profile",
                    entity_id=candidate.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"You already have {MAX_ACTIVE_APPLICATIONS_PER_CANDIDATE} active opportunities in progress. "
                            "Close one of the active decisions before I ask you to review more roles."
                        ),
                    },
                    allow_duplicate=True,
                )
            return {
                "status": "candidate_cap_reached",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": 0,
                "promoted_count": 0,
                "notified": force,
            }

        current_batch = list(
            self.matches.list_pre_interview_review_for_candidate(
                candidate.id,
                limit=presentation_limit,
            )
        )
        preexisting_count = len(current_batch)
        current_batch_ids = {match.id for match in current_batch}
        newly_promoted: list = []
        promoted_count = 0
        if len(current_batch) < presentation_limit:
            shortlisted = self.matches.list_shortlisted_for_candidate(
                candidate.id,
                limit=MATCH_BATCH_SIZE * 4,
            )
            for match in shortlisted:
                if match.id in current_batch_ids:
                    continue
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
                    trigger_type=trigger_type,
                    state_field="status",
                    metadata_json={
                        "candidate_profile_id": str(candidate.id),
                        "presentation": "candidate_vacancy_review",
                    },
                )
                current_batch.append(match)
                current_batch_ids.add(match.id)
                newly_promoted.append(match)
                promoted_count += 1
                if len(current_batch) >= presentation_limit:
                    break

        if not current_batch:
            return {
                "status": "empty",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": 0,
                "promoted_count": promoted_count,
                "notified": False,
            }

        if promoted_count == 0 and preexisting_count > 0:
            return {
                "status": "already_presented",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": len(current_batch),
                "promoted_count": promoted_count,
                "notified": False,
            }

        notification_batch = current_batch if preexisting_count == 0 else newly_promoted
        self.notifications.create(
            user_id=candidate.user_id,
            entity_type="candidate_profile",
            entity_id=candidate.id,
            template_key="candidate_vacancy_review_ready",
            payload_json={
                "message_entries": self._build_candidate_batch_entries(batch=notification_batch),
            },
            allow_duplicate=True,
        )
        return {
            "status": "dispatched",
            "candidate_profile_id": str(candidate_profile_id),
            "batch_count": len(current_batch),
            "notified_count": len(notification_batch),
            "promoted_count": promoted_count,
            "notified": True,
        }

    def current_batch_size_for_candidate(self, *, candidate_user_id) -> int:
        candidate = self.candidates.get_active_by_user_id(candidate_user_id)
        if candidate is None:
            return 0
        latest = self.matches.get_latest_pre_interview_review_for_candidate(candidate.id)
        if latest is None:
            return 0
        return len(self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=MATCH_BATCH_SIZE))

    def execute_candidate_pre_interview_action(
        self,
        *,
        user,
        raw_message_id,
        action: str,
        vacancy_slot: Optional[int],
        match_id: Optional[str] = None,
    ) -> Optional[CandidateVacancyActionResult]:
        if not getattr(user, "is_candidate", False):
            return None

        candidate = self.candidates.get_active_by_user_id(user.id)
        if candidate is None:
            return None

        batch = self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=MATCH_BATCH_SIZE)
        match = self.matches.get_by_id(match_id) if match_id else None
        if match is not None:
            if not batch or all(vacancy_match.id != match.id for vacancy_match in batch):
                self.notifications.create(
                    user_id=user.id,
                    entity_type="candidate_profile",
                    entity_id=candidate.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            "That vacancy card is no longer active. Use the latest buttons under the current vacancy cards."
                        ),
                    },
                    allow_duplicate=True,
                )
                return CandidateVacancyActionResult(status="invalid_match")
        elif not batch or vacancy_slot is None or vacancy_slot < 1 or vacancy_slot > len(batch):
            self.notifications.create(
                user_id=user.id,
                entity_type="candidate_profile",
                entity_id=candidate.id,
                template_key="candidate_vacancy_review_ready",
                payload_json={
                    "text": self._copy(
                        "That option is no longer valid. Use the latest buttons under the current vacancy cards."
                    ),
                },
                allow_duplicate=True,
            )
            return CandidateVacancyActionResult(status="invalid_slot")

        if match is None:
            match = batch[vacancy_slot - 1]
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if vacancy is None:
            return None

        role_title = getattr(vacancy, "role_title", None) or "this role"
        manager_user = self.users.get_by_id(getattr(vacancy, "manager_user_id", None))
        candidate_user = self.users.get_by_id(getattr(candidate, "user_id", None))
        shared_contacts = False

        if action == "apply_to_vacancy":
            if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_APPROVED,
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=user.id,
                    state_field="status",
                    metadata_json={"vacancy_id": str(vacancy.id), "source": "candidate_direct_connect"},
                )
                self._share_contacts(
                    match=match,
                    candidate_user=candidate_user,
                    manager_user=manager_user,
                    vacancy=vacancy,
                    candidate_text=self._copy(
                        f"You and the hiring manager both approved {role_title}. Here is the manager contact for the next step."
                    ),
                    manager_text=self._copy(
                        f"{candidate_user.display_name if candidate_user and getattr(candidate_user, 'display_name', None) else 'The candidate'} accepted the connection for {role_title}. Here is the candidate contact for the next step."
                    ),
                )
                status = "approved"
                shared_contacts = True
            else:
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_CANDIDATE_APPLIED,
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=user.id,
                    state_field="status",
                    metadata_json={"vacancy_id": str(vacancy.id), "source": "candidate_vacancy_review"},
                )
                self.notifications.create(
                    user_id=user.id,
                    entity_type="match",
                    entity_id=match.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"Applied to {role_title}. I sent your profile to the hiring manager for review."
                        ),
                    },
                    allow_duplicate=True,
                )
                self.dispatch_manager_batch_for_vacancy(
                    vacancy_id=vacancy.id,
                    force=True,
                    trigger_type="user_action",
                )
                status = "applied"
        elif action == "skip_vacancy":
            previous_status = getattr(match, "status", None)
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state=MATCH_STATUS_CANDIDATE_SKIPPED,
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=user.id,
                state_field="status",
                metadata_json={"vacancy_id": str(vacancy.id), "source": "candidate_vacancy_review"},
            )
            self.notifications.create(
                user_id=user.id,
                entity_type="match",
                entity_id=match.id,
                template_key="candidate_vacancy_review_ready",
                payload_json={
                    "text": self._copy(f"Skipped {role_title}."),
                },
                allow_duplicate=True,
            )
            if previous_status == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
                self.notifications.create(
                    user_id=getattr(vacancy, "manager_user_id", None),
                    entity_type="match",
                    entity_id=match.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"{candidate_user.display_name if candidate_user and getattr(candidate_user, 'display_name', None) else 'The candidate'} skipped the approved opportunity for {role_title}."
                        ),
                    },
                    allow_duplicate=True,
                )
            status = "skipped"
        else:
            return None

        batch_result = self.dispatch_candidate_batch_for_profile(
            candidate_profile_id=candidate.id,
            force=True,
            trigger_type="user_action",
        )
        if batch_result["status"] == "candidate_cap_reached":
            return CandidateVacancyActionResult(status=status)
        if batch_result["batch_count"] == 0 and not shared_contacts:
            self.notifications.create(
                user_id=user.id,
                entity_type="candidate_profile",
                entity_id=candidate.id,
                template_key="candidate_vacancy_review_ready",
                payload_json={
                    "text": self._copy(
                        "That was the last vacancy in the current batch. I will send more roles as soon as matching produces them."
                    ),
                },
                allow_duplicate=True,
            )
        return CandidateVacancyActionResult(status=status)

    def execute_manager_pre_interview_action(
        self,
        *,
        user,
        raw_message_id,
        action: str,
        candidate_slot: Optional[int],
        match_id: Optional[str] = None,
    ) -> Optional[ManagerPreInterviewActionResult]:
        if not getattr(user, "is_hiring_manager", False):
            return None

        vacancy_ids = [vacancy.id for vacancy in self.vacancies.get_by_manager_user_id(user.id)]
        latest = self.matches.get_latest_pre_interview_review_for_manager(vacancy_ids)
        if latest is None and not match_id:
            return None

        match = self.matches.get_by_id(match_id) if match_id else None
        vacancy = self.vacancies.get_by_id(match.vacancy_id) if match is not None else None
        if vacancy is None and latest is not None:
            vacancy = self.vacancies.get_by_id(latest.vacancy_id)
        if vacancy is None:
            return None
        if vacancy.id not in vacancy_ids:
            return None

        batch = self.matches.list_pre_interview_review_for_vacancy(
            vacancy.id,
            limit=MATCH_BATCH_SIZE,
        )
        if match is not None:
            if not batch or all(candidate_match.id != match.id for candidate_match in batch):
                self.notifications.create(
                    user_id=user.id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            "That candidate card is no longer active. Use the latest buttons under the current candidate cards."
                        ),
                    },
                    allow_duplicate=True,
                )
                return ManagerPreInterviewActionResult(status="invalid_match")
        elif not batch or candidate_slot is None or candidate_slot < 1 or candidate_slot > len(batch):
            self.notifications.create(
                user_id=user.id,
                entity_type="vacancy",
                entity_id=vacancy.id,
                template_key="manager_pre_interview_review_ready",
                payload_json={
                    "text": self._copy(
                        "That option is no longer valid. Use the latest buttons under the current candidate cards."
                    ),
                },
                allow_duplicate=True,
            )
            return ManagerPreInterviewActionResult(status="invalid_slot")

        if match is None:
            match = batch[candidate_slot - 1]
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        if candidate is None:
            return None

        candidate_name = self._candidate_label(candidate)
        previous_status = getattr(match, "status", None)
        role_title = getattr(vacancy, "role_title", None) or "this vacancy"
        candidate_user = self.users.get_by_id(candidate.user_id)
        shared_contacts = False

        if action == "interview_candidate":
            if previous_status != MATCH_STATUS_CANDIDATE_APPLIED and self._manager_batch_limit(vacancy.id) <= 0:
                self.notifications.create(
                    user_id=user.id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"You already have {MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY} candidates "
                            "already active on this vacancy. "
                            "Close one of those active decisions before approving another candidate."
                        ),
                    },
                    allow_duplicate=True,
                )
                return ManagerPreInterviewActionResult(status="vacancy_cap_reached")
            if previous_status == MATCH_STATUS_CANDIDATE_APPLIED:
                manager_user = self.users.get_by_id(user.id)
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_APPROVED,
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=user.id,
                    state_field="status",
                    metadata_json={"vacancy_id": str(vacancy.id), "source": "manager_direct_connect"},
                )
                self._share_contacts(
                    match=match,
                    candidate_user=candidate_user,
                    manager_user=manager_user,
                    vacancy=vacancy,
                    candidate_text=self._copy(
                        f"You and the hiring manager both approved {role_title}. Here is the manager contact for the next step."
                    ),
                    manager_text=self._copy(
                        f"You and {candidate_name} both approved this match for {role_title}. Here is the candidate contact for the next step."
                    ),
                )
                status = "approved"
                shared_contacts = True
            else:
                self.state_service.transition(
                    entity_type="match",
                    entity=match,
                    to_state=MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=user.id,
                    state_field="status",
                    metadata_json={"vacancy_id": str(vacancy.id), "source": "manager_pre_interview_review"},
                )
                self.notifications.create(
                    user_id=candidate.user_id,
                    entity_type="match",
                    entity_id=match.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "message_entries": [
                            {
                                "text": self._copy(
                                    f"The hiring manager already approved you for {role_title}. "
                                    "If you still want to move forward, tap Connect and I will share contacts right away."
                                ),
                            },
                            {
                                "text": self._render_vacancy_card_message(match=match, slot_no=None),
                                "reply_markup": candidate_vacancy_inline_keyboard(
                                    match_id=str(match.id),
                                    primary_text="Connect",
                                ),
                            },
                        ],
                    },
                    allow_duplicate=True,
                )
                self.notifications.create(
                    user_id=user.id,
                    entity_type="match",
                    entity_id=match.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"{candidate_name} is approved on your side. I asked the candidate to confirm, and I'll share contacts if they agree."
                        ),
                    },
                    allow_duplicate=True,
                )
                status = "awaiting_candidate"
        elif action == "skip_candidate":
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state=MATCH_STATUS_MANAGER_SKIPPED,
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=user.id,
                state_field="status",
                metadata_json={"vacancy_id": str(vacancy.id), "source": "manager_pre_interview_review"},
            )
            self.notifications.create(
                user_id=user.id,
                entity_type="match",
                entity_id=match.id,
                template_key="manager_pre_interview_review_ready",
                payload_json={
                    "text": self._copy(f"Skipped {candidate_name} for this vacancy."),
                },
                allow_duplicate=True,
            )
            if previous_status == MATCH_STATUS_CANDIDATE_APPLIED:
                self.notifications.create(
                    user_id=candidate.user_id,
                    entity_type="match",
                    entity_id=match.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"The hiring manager decided not to move forward with {role_title}."
                        ),
                    },
                    allow_duplicate=True,
                )
            status = "skipped"
        else:
            return None

        batch_result = self.dispatch_manager_batch_for_vacancy(
            vacancy_id=vacancy.id,
            force=True,
            trigger_type="user_action",
        )
        if batch_result["status"] == "vacancy_cap_reached":
            return ManagerPreInterviewActionResult(status=status)
        if batch_result["batch_count"] == 0 and not shared_contacts:
            self.notifications.create(
                user_id=user.id,
                entity_type="vacancy",
                entity_id=vacancy.id,
                template_key="manager_pre_interview_review_ready",
                payload_json={
                    "text": self._copy(
                        "That was the last candidate in the current review batch. I will send more as soon as matching produces them."
                    ),
                },
                allow_duplicate=True,
            )
        return ManagerPreInterviewActionResult(status=status)
