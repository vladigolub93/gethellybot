from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.users import UsersRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.messaging.service import MessagingService
from src.candidate_profile.work_formats import display_work_formats
from src.llm.service import (
    safe_answer_candidate_review_object_question,
    safe_answer_manager_review_object_question,
)
from src.matching.dossier import (
    build_candidate_review_dossier,
    build_manager_review_dossier,
)
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
from src.shared.hiring_taxonomy import display_domains, display_english_level, display_hiring_stages


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
    def _feedback_context(context_json: dict | None) -> dict:
        current = dict(context_json or {})
        feedback = dict(current.get("matching_feedback") or {})
        feedback.setdefault("candidate_skip_streak", 0)
        feedback.setdefault("manager_skip_streak", 0)
        current["matching_feedback"] = feedback
        return current

    def _record_candidate_skip(self, candidate) -> int:
        context = self._feedback_context(getattr(candidate, "questions_context_json", None))
        feedback = context["matching_feedback"]
        feedback["candidate_skip_streak"] = int(feedback.get("candidate_skip_streak") or 0) + 1
        self.candidates.update_questions_context(candidate, context)
        return int(feedback["candidate_skip_streak"])

    def _reset_candidate_skip_streak(self, candidate) -> None:
        context = self._feedback_context(getattr(candidate, "questions_context_json", None))
        if context["matching_feedback"].get("candidate_skip_streak", 0) == 0:
            return
        context["matching_feedback"]["candidate_skip_streak"] = 0
        self.candidates.update_questions_context(candidate, context)

    def _record_manager_skip(self, vacancy) -> int:
        context = self._feedback_context(getattr(vacancy, "questions_context_json", None))
        feedback = context["matching_feedback"]
        feedback["manager_skip_streak"] = int(feedback.get("manager_skip_streak") or 0) + 1
        self.vacancies.update_questions_context(vacancy, context)
        return int(feedback["manager_skip_streak"])

    def _reset_manager_skip_streak(self, vacancy) -> None:
        context = self._feedback_context(getattr(vacancy, "questions_context_json", None))
        if context["matching_feedback"].get("manager_skip_streak", 0) == 0:
            return
        context["matching_feedback"]["manager_skip_streak"] = 0
        self.vacancies.update_questions_context(vacancy, context)

    @staticmethod
    def _should_prompt_skip_feedback(streak: int) -> bool:
        return streak >= 3 and streak % 3 == 0

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

    @staticmethod
    def _normalize_sentence(value: str | None) -> str | None:
        if not value:
            return None
        text = " ".join(str(value).split()).strip()
        if not text:
            return None
        return text if text.endswith((".", "!", "?")) else f"{text}."

    @classmethod
    def _lower_lead(cls, value: str | None) -> str | None:
        normalized = cls._normalize_sentence(value)
        if not normalized:
            return None
        if len(normalized) == 1:
            return normalized.lower()
        return normalized[:1].lower() + normalized[1:].rstrip(".")

    @staticmethod
    def _join_with_and(values: list[str]) -> str:
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        return f"{', '.join(values[:-1])} and {values[-1]}"

    @staticmethod
    def _effective_hiring_stages(vacancy) -> list[str]:
        hiring_stages = display_hiring_stages(getattr(vacancy, "hiring_stages_json", None))
        if not hiring_stages:
            return []
        if getattr(vacancy, "has_take_home_task", None) is False:
            hiring_stages = [stage for stage in hiring_stages if stage.lower() != "take-home task"]
        if getattr(vacancy, "has_live_coding", None) is False:
            hiring_stages = [stage for stage in hiring_stages if stage.lower() != "live coding"]
        return hiring_stages

    @staticmethod
    def _has_cyrillic(text: str | None) -> bool:
        if not text:
            return False
        return bool(re.search(r"[А-Яа-яЁёІіЇїЄєҐґ]", text))

    @staticmethod
    def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
        lowered = (text or "").lower()
        return any(token in lowered for token in tokens)

    def _looks_like_review_flow_question(self, text: str | None) -> bool:
        if not text:
            return False
        return self._contains_any(
            text,
            (
                "what happens after",
                "what if i apply",
                "what if i connect",
                "what if i skip",
                "how does this work",
                "how does helly work",
                "как это работает",
                "что будет после",
                "что будет если",
                "что дальше после",
                "что будет после apply",
                "что будет после connect",
                "что будет после skip",
            ),
        )

    def _looks_like_review_object_question(self, text: str | None) -> bool:
        normalized = " ".join((text or "").split()).strip().lower()
        if not normalized:
            return False
        if self._looks_like_review_flow_question(normalized):
            return False
        if "?" in normalized:
            return True
        return self._contains_any(
            normalized,
            (
                "detail",
                "details",
                "more",
                "about",
                "project",
                "product",
                "domain",
                "role",
                "responsibil",
                "stack",
                "tech",
                "budget",
                "salary",
                "comp",
                "rate",
                "format",
                "remote",
                "hybrid",
                "office",
                "location",
                "city",
                "country",
                "english",
                "process",
                "stage",
                "interview",
                "take-home",
                "take home",
                "live coding",
                "why",
                "fit",
                "showed",
                "show this",
                "candidate",
                "profile",
                "skill",
                "skills",
                "summary",
                "experience",
                "assessment",
                "team",
                "company",
                "benefit",
                "benefits",
                "visa",
                "relocat",
                "contract",
                "availability",
                "notice",
                "verified",
                "verification",
                "evaluation",
                "score",
                "strength",
                "risk",
                "github",
                "linkedin",
                "portfolio",
                "education",
                "cert",
                "детал",
                "подроб",
                "проект",
                "продукт",
                "домен",
                "роль",
                "задач",
                "стек",
                "технолог",
                "бюдж",
                "зарплат",
                "ставк",
                "формат",
                "удален",
                "гибрид",
                "офис",
                "локац",
                "город",
                "страна",
                "англий",
                "процесс",
                "этап",
                "собес",
                "лайвкод",
                "тестов",
                "таск",
                "почему",
                "зачем",
                "кандидат",
                "профил",
                "скилл",
                "опыт",
                "саммар",
                "команд",
                "компан",
                "бенефит",
                "виз",
                "релок",
                "контракт",
                "доступ",
                "вериф",
                "оценк",
                "скор",
                "сильн",
                "риск",
                "образован",
                "сертиф",
                "портф",
                "гитхаб",
                "линкедин",
            ),
        )

    @staticmethod
    def _format_country_codes(codes: list[str] | None) -> str | None:
        values = [str(code).strip().upper() for code in (codes or []) if str(code).strip()]
        if not values:
            return None
        return ", ".join(values[:6])

    def _vacancy_setup_details(self, vacancy, *, ru: bool) -> str | None:
        parts: list[str] = []
        work_format = getattr(vacancy, "work_format", None)
        office_city = getattr(vacancy, "office_city", None)
        countries = self._format_country_codes(getattr(vacancy, "countries_allowed_json", None))
        if work_format:
            parts.append(f"формат {work_format}" if ru else f"{work_format} setup")
        if office_city:
            parts.append(f"город {office_city}" if ru else f"office city {office_city}")
        if countries:
            parts.append(f"страны {countries}" if ru else f"allowed countries {countries}")
        if not parts:
            return None
        if ru:
            return "По формату и локации вижу: " + "; ".join(parts) + "."
        return "For format and location I have: " + "; ".join(parts) + "."

    def _vacancy_process_details(self, vacancy, *, ru: bool) -> str | None:
        parts: list[str] = []
        english_level = display_english_level(getattr(vacancy, "required_english_level", None))
        if english_level:
            parts.append(f"English {english_level}")
        hiring_stages = self._effective_hiring_stages(vacancy)
        if hiring_stages:
            parts.append(
                ("этапы " + ", ".join(hiring_stages[:5])) if ru else ("stages " + ", ".join(hiring_stages[:5]))
            )
        take_home = getattr(vacancy, "has_take_home_task", None)
        if take_home is True:
            paid = getattr(vacancy, "take_home_paid", None)
            if ru:
                if paid is True:
                    parts.append("есть оплачиваемая тестовая задача")
                elif paid is False:
                    parts.append("есть неоплачиваемая тестовая задача")
                else:
                    parts.append("есть тестовая задача")
            else:
                if paid is True:
                    parts.append("a paid take-home task")
                elif paid is False:
                    parts.append("an unpaid take-home task")
                else:
                    parts.append("a take-home task")
        elif take_home is False:
            parts.append("тестовой задачи нет" if ru else "no take-home task")
        live_coding = getattr(vacancy, "has_live_coding", None)
        if live_coding is True:
            parts.append("есть live coding" if ru else "live coding")
        elif live_coding is False:
            parts.append("live coding нет" if ru else "no live coding")
        if not parts:
            return None
        if ru:
            return "По процессу вижу: " + "; ".join(parts) + "."
        return "For process details I have: " + "; ".join(parts) + "."

    def _candidate_preferences_details(self, candidate, *, ru: bool) -> str | None:
        parts: list[str] = []
        salary = self._candidate_salary_label(candidate)
        if salary:
            parts.append(f"ожидание по компенсации {salary}" if ru else f"compensation expectation {salary}")
        location = getattr(candidate, "location_text", None)
        if location:
            parts.append(f"локация {location}" if ru else f"location {location}")
        work_formats = display_work_formats(candidate)
        if work_formats:
            parts.append(f"формат {work_formats}" if ru else f"preferred work format {work_formats}")
        english = display_english_level(getattr(candidate, "english_level", None))
        if english:
            parts.append(f"English {english}")
        domains = display_domains(getattr(candidate, "preferred_domains_json", None))
        if domains:
            parts.append(
                ("домены " + ", ".join(domains[:5])) if ru else ("preferred domains " + ", ".join(domains[:5]))
            )
        if not parts:
            return None
        if ru:
            return "По сохраненным предпочтениям вижу: " + "; ".join(parts) + "."
        return "From saved preferences I have: " + "; ".join(parts) + "."

    def _candidate_assessment_preferences_details(self, candidate, *, ru: bool) -> str | None:
        parts: list[str] = []
        show_take_home = getattr(candidate, "show_take_home_task_roles", None)
        if show_take_home is True:
            parts.append("готов к take-home" if ru else "take-home roles are okay")
        elif show_take_home is False:
            parts.append("take-home роли скрыты" if ru else "take-home roles are hidden")
        show_live = getattr(candidate, "show_live_coding_roles", None)
        if show_live is True:
            parts.append("готов к live coding" if ru else "live-coding roles are okay")
        elif show_live is False:
            parts.append("live-coding роли скрыты" if ru else "live-coding roles are hidden")
        if not parts:
            return None
        if ru:
            return "По этапам оценки вижу: " + "; ".join(parts) + "."
        return "For assessment preferences I have: " + "; ".join(parts) + "."

    def _current_candidate_review_context(self, *, user):
        candidate = self.candidates.get_active_by_user_id(user.id)
        if candidate is None:
            return None
        review_matches = self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=1)
        if not review_matches:
            return None
        match = review_matches[0]
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if vacancy is None:
            return None
        version = self.vacancies.get_current_version(vacancy) or self.vacancies.get_version_by_id(
            getattr(match, "vacancy_version_id", None)
        )
        return candidate, match, vacancy, version

    def _current_manager_review_context(self, *, user):
        vacancy_ids = [vacancy.id for vacancy in self.vacancies.get_by_manager_user_id(user.id)]
        latest = self.matches.get_latest_pre_interview_review_for_manager(vacancy_ids)
        if latest is None:
            return None
        vacancy = self.vacancies.get_by_id(latest.vacancy_id)
        if vacancy is None or getattr(vacancy, "manager_user_id", None) != user.id:
            return None
        review_matches = self.matches.list_pre_interview_review_for_vacancy(vacancy.id, limit=1)
        if not review_matches:
            return None
        match = review_matches[0]
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        if candidate is None:
            return None
        version = self.candidates.get_current_version(candidate) or self.candidates.get_version_by_id(
            getattr(match, "candidate_profile_version_id", None)
        )
        return vacancy, match, candidate, version

    def _manager_vacancies_for_user(self, manager_user_id) -> list:
        getter = getattr(self.vacancies, "get_open_by_manager_user_id", None)
        vacancies = getter(manager_user_id) if callable(getter) else self.vacancies.get_by_manager_user_id(manager_user_id)
        return [vacancy for vacancy in (vacancies or []) if getattr(vacancy, "deleted_at", None) is None]

    def _current_manager_review_match_for_user(self, manager_user_id):
        vacancy_ids = [vacancy.id for vacancy in self._manager_vacancies_for_user(manager_user_id)]
        if not vacancy_ids:
            return None
        return self.matches.get_latest_pre_interview_review_for_manager(vacancy_ids)

    def _current_candidate_review_match_for_user(self, candidate_user_id):
        candidate = self.candidates.get_active_by_user_id(candidate_user_id)
        if candidate is None:
            return None
        review_matches = self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=1)
        return review_matches[0] if review_matches else None

    def _ordered_manager_vacancies(self, *, manager_user_id, preferred_vacancy_id=None) -> list:
        vacancies = self._manager_vacancies_for_user(manager_user_id)
        if preferred_vacancy_id is None:
            return vacancies
        preferred: list = []
        rest: list = []
        for vacancy in vacancies:
            if str(getattr(vacancy, "id", "")) == str(preferred_vacancy_id):
                preferred.append(vacancy)
            else:
                rest.append(vacancy)
        return preferred + rest

    def _collect_shortlisted_matches_for_manager(self, *, manager_user_id, preferred_vacancy_id=None) -> list:
        ranked: list = []
        seen: set[str] = set()
        for vacancy in self._ordered_manager_vacancies(
            manager_user_id=manager_user_id,
            preferred_vacancy_id=preferred_vacancy_id,
        ):
            if self._manager_batch_limit(vacancy.id) <= 0:
                continue
            for match in self.matches.list_shortlisted_for_vacancy(vacancy.id, limit=MATCH_BATCH_SIZE * 2):
                key = str(getattr(match, "id", ""))
                if not key or key in seen:
                    continue
                seen.add(key)
                ranked.append(match)
        return self._sort_matches_for_manager_review(ranked)

    def _matches_more_queue_request(self, text: str | None, *, audience: str) -> bool:
        normalized = " ".join((text or "").split()).strip().lower()
        if not normalized:
            return False
        if audience == "candidate":
            groups = (
                ("more", "role"),
                ("more", "vacanc"),
                ("another", "role"),
                ("another", "vacanc"),
                ("next", "role"),
                ("next", "vacanc"),
                ("ещ", "ваканс"),
                ("ещ", "рол"),
                ("друг", "ваканс"),
                ("следующ", "ваканс"),
                ("следующ", "рол"),
                ("покажи", "ваканс"),
                ("дай", "ваканс"),
            )
        else:
            groups = (
                ("more", "candidate"),
                ("another", "candidate"),
                ("next", "candidate"),
                ("ещ", "кандид"),
                ("друг", "кандид"),
                ("следующ", "кандид"),
                ("покажи", "кандид"),
                ("дай", "кандид"),
                ("more", "profile"),
                ("another", "profile"),
            )
        return any(all(part in normalized for part in group) for group in groups)

    def block_candidate_more_request(self, *, user, text: str) -> str | None:
        if self._current_candidate_review_match_for_user(user.id) is None:
            return None
        if not self._matches_more_queue_request(text, audience="candidate"):
            return None
        ru = self._has_cyrillic(text)
        if ru:
            return (
                "Сначала нужно принять решение по текущей вакансии: Connect или Skip. "
                "Как только закроем эту карточку, я сразу покажу следующую из очереди."
            )
        return (
            "First, decide on the current vacancy card with Apply/Connect or Skip. "
            "As soon as this card is resolved, I’ll show the next one in the queue."
        )

    def block_manager_more_request(self, *, user, text: str) -> str | None:
        if self._current_manager_review_match_for_user(user.id) is None:
            return None
        if not self._matches_more_queue_request(text, audience="manager"):
            return None
        ru = self._has_cyrillic(text)
        if ru:
            return (
                "Сначала нужно принять решение по текущему кандидату: Connect или Skip. "
                "Как только закроем эту карточку, я покажу следующего кандидата из очереди."
            )
        return (
            "First, decide on the current candidate card with Connect or Skip. "
            "As soon as this card is resolved, I’ll show the next candidate in the queue."
        )

    def _candidate_review_dossier_answer(self, *, question_text: str, match, vacancy, vacancy_version) -> str | None:
        dossier = build_candidate_review_dossier(
            match=match,
            vacancy=vacancy,
            vacancy_version=vacancy_version,
        )
        result = safe_answer_candidate_review_object_question(
            self.session,
            question_text=question_text,
            dossier=dossier,
        )
        message = str((result.payload or {}).get("message") or "").strip()
        return message or None

    def _manager_review_dossier_answer(self, *, question_text: str, match, vacancy, candidate, candidate_version) -> str | None:
        dossier = build_manager_review_dossier(
            match=match,
            vacancy=vacancy,
            candidate=candidate,
            candidate_version=candidate_version,
            latest_verification=self.verifications.get_latest_submitted_by_profile_id(candidate.id),
            evaluation_result=self.evaluations.get_by_match_id(match.id),
        )
        result = safe_answer_manager_review_object_question(
            self.session,
            question_text=question_text,
            dossier=dossier,
        )
        message = str((result.payload or {}).get("message") or "").strip()
        return message or None

    def answer_candidate_review_question(self, *, user, question_text: str) -> str | None:
        if not self._looks_like_review_object_question(question_text):
            return None
        context = self._current_candidate_review_context(user=user)
        if context is None:
            return None
        candidate, match, vacancy, vacancy_version = context
        ru = self._has_cyrillic(question_text)
        lowered = (question_text or "").lower()
        role_title = getattr(vacancy, "role_title", None) or ("эта роль" if ru else "this role")
        summary = self._truncate_text(
            getattr(vacancy_version, "approval_summary_text", None)
            or ((getattr(vacancy_version, "summary_json", None) or {}).get("approval_summary_text") if vacancy_version else None),
            limit=240,
        )
        project = self._truncate_text(getattr(vacancy, "project_description", None), limit=240)
        stack = list(getattr(vacancy, "primary_tech_stack_json", None) or [])[:8]
        budget = self._vacancy_budget_label(vacancy)
        setup = self._vacancy_setup_details(vacancy, ru=ru)
        process = self._vacancy_process_details(vacancy, ru=ru)
        fit_reason = self._match_reason_text(match)
        gap_context = self._match_gap_context(match)

        if self._contains_any(lowered, ("why", "fit", "showed", "selected", "почему", "зачем", "показал", "подходит")):
            parts = []
            if fit_reason:
                parts.append(("Почему показал: " + fit_reason) if ru else ("Why I showed it: " + fit_reason))
            if gap_context:
                parts.append(("Компромисс по карточке: " + gap_context) if ru else ("Tradeoff on this match: " + gap_context))
            if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
                parts.append(
                    "Отдельно вижу, что менеджер уже одобрил этот матч."
                    if ru
                    else "I also see that the hiring manager already approved this match."
                )
            if parts:
                return " ".join(parts)

        if self._contains_any(lowered, ("project", "product", "domain", "о чем", "проект", "продукт", "домен")):
            if project:
                return (
                    f"По {role_title} у меня сохранено такое описание проекта: {project}"
                    if ru
                    else f"For {role_title}, the saved project description is: {project}"
                )
            if summary:
                return (
                    f"Отдельного описания проекта по {role_title} у меня нет, но в summary сохранено: {summary}"
                    if ru
                    else f"I do not have a separate project description for {role_title}, but the saved summary says: {summary}"
                )

        if self._contains_any(lowered, ("budget", "salary", "comp", "rate", "бюдж", "зарплат", "ставк", "деньг")):
            if budget:
                return (
                    f"По этой вакансии вижу бюджет {budget}."
                    if ru
                    else f"For this role, I have the budget saved as {budget}."
                )
            return (
                "По этой вакансии бюджет у меня не сохранен."
                if ru
                else "I do not have a saved budget for this role."
            )

        if self._contains_any(lowered, ("stack", "tech", "skill", "skills", "стек", "технолог", "скилл")):
            if stack:
                return (
                    "По стеку у меня сохранено: " + ", ".join(stack) + "."
                    if ru
                    else "For the stack, I have: " + ", ".join(stack) + "."
                )
            return (
                "По этой карточке стек отдельно не сохранен."
                if ru
                else "I do not have a separate stack list saved on this card."
            )

        if self._contains_any(lowered, ("format", "remote", "hybrid", "office", "location", "city", "country", "формат", "локац", "город", "страна")):
            if setup:
                return setup
            return (
                "По формату и локации в этой карточке у меня только базовые поля без дополнительных ограничений."
                if ru
                else "For format and location, I only have the basic card fields without extra constraints."
            )

        if self._contains_any(lowered, ("english", "англий")):
            english_level = display_english_level(getattr(vacancy, "required_english_level", None))
            if english_level:
                return (
                    f"По этой вакансии нужен английский примерно на уровне {english_level}."
                    if ru
                    else f"This role currently requires around {english_level} English."
                )
            return (
                "По этой вакансии уровень английского у меня не сохранен."
                if ru
                else "I do not have a saved English requirement for this role."
            )

        if self._contains_any(lowered, ("process", "stage", "interview", "take-home", "take home", "live coding", "процесс", "этап", "собес", "тестов", "таск", "лайвкод")):
            if process:
                return process
            return (
                "По процессу у меня в этой карточке только базовые поля без дополнительных деталей."
                if ru
                else "For process details, I only have the basic fields on this card."
            )

        rag_answer = self._candidate_review_dossier_answer(
            question_text=question_text,
            match=match,
            vacancy=vacancy,
            vacancy_version=vacancy_version,
        )
        if rag_answer:
            return rag_answer

        parts = []
        if project:
            parts.append(
                f"По проекту вижу: {project}"
                if ru
                else f"For the project, I have: {project}"
            )
        elif summary:
            parts.append(
                f"По summary вижу: {summary}"
                if ru
                else f"From the saved summary, I have: {summary}"
            )
        if budget:
            parts.append(
                f"Бюджет: {budget}"
                if ru
                else f"Budget: {budget}"
            )
        if setup:
            parts.append(setup.rstrip("."))
        if stack:
            parts.append(
                "Стек: " + ", ".join(stack)
                if ru
                else "Stack: " + ", ".join(stack)
            )
        if process:
            parts.append(process.rstrip("."))
        if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
            parts.append(
                "Менеджер уже одобрил этот матч."
                if ru
                else "The hiring manager already approved this match."
            )
        if not parts:
            return (
                "По этой карточке у меня сейчас есть только базовые поля без дополнительных деталей."
                if ru
                else "On this card, I currently only have the basic saved fields without extra details."
            )
        return " ".join(parts)

    def answer_manager_review_question(self, *, user, question_text: str) -> str | None:
        if not self._looks_like_review_object_question(question_text):
            return None
        context = self._current_manager_review_context(user=user)
        if context is None:
            return None
        vacancy, match, candidate, candidate_version = context
        candidate_user = self.users.get_by_id(getattr(candidate, "user_id", None))
        ru = self._has_cyrillic(question_text)
        lowered = (question_text or "").lower()
        candidate_name = (
            getattr(candidate_user, "display_name", None)
            or getattr(candidate_user, "username", None)
            or ("кандидат" if ru else "the candidate")
        )
        summary_json = getattr(candidate_version, "summary_json", None) or {}
        summary_text = self._truncate_text(summary_json.get("approval_summary_text") or summary_json.get("headline"), limit=240)
        years = summary_json.get("years_experience")
        skills = list(summary_json.get("skills") or [])[:8]
        preferences = self._candidate_preferences_details(candidate, ru=ru)
        assessments = self._candidate_assessment_preferences_details(candidate, ru=ru)
        fit_reason = self._match_reason_text(match)
        gap_context = self._match_gap_context(match)

        if self._contains_any(lowered, ("why", "fit", "showed", "selected", "почему", "зачем", "показал", "подходит")):
            parts = []
            if fit_reason:
                parts.append(("Почему я показал этого кандидата: " + fit_reason) if ru else ("Why I showed this candidate: " + fit_reason))
            if gap_context:
                parts.append(("Основной tradeoff: " + gap_context) if ru else ("Main tradeoff: " + gap_context))
            if parts:
                return " ".join(parts)

        if self._contains_any(lowered, ("summary", "background", "experience", "опыт", "бэкгра", "саммар")):
            if summary_text:
                return (
                    f"По {candidate_name} у меня сохранено такое summary: {summary_text}"
                    if ru
                    else f"For {candidate_name}, the saved summary is: {summary_text}"
                )
            if years is not None or skills:
                parts = []
                if years is not None:
                    parts.append(f"{int(years)}+ лет опыта" if ru else f"{int(years)}+ years of experience")
                if skills:
                    parts.append(("скиллы " + ", ".join(skills)) if ru else ("skills " + ", ".join(skills)))
                return (
                    f"По {candidate_name} вижу: " + "; ".join(parts) + "."
                    if ru
                    else f"For {candidate_name}, I have: " + "; ".join(parts) + "."
                )

        if self._contains_any(lowered, ("stack", "tech", "skill", "skills", "стек", "технолог", "скилл")):
            if skills:
                return (
                    f"По {candidate_name} в сохраненных данных вижу скиллы: " + ", ".join(skills) + "."
                    if ru
                    else f"For {candidate_name}, the saved skills are: " + ", ".join(skills) + "."
                )
            return (
                "По этой карточке список скиллов отдельно не сохранен."
                if ru
                else "I do not have a separate skill list saved on this card."
            )

        if self._contains_any(lowered, ("budget", "salary", "comp", "rate", "зарплат", "ставк", "бюдж", "деньг")):
            salary = self._candidate_salary_label(candidate)
            if salary:
                return (
                    f"По {candidate_name} вижу ожидание по компенсации {salary}."
                    if ru
                    else f"For {candidate_name}, the saved compensation expectation is {salary}."
                )
            return (
                "По этой карточке ожидание по компенсации не сохранено."
                if ru
                else "I do not have a saved compensation expectation on this card."
            )

        if self._contains_any(lowered, ("format", "remote", "hybrid", "office", "location", "city", "country", "формат", "локац", "город", "страна")):
            if preferences:
                return preferences
            return (
                "По локации и формату в этой карточке у меня только базовые поля."
                if ru
                else "For location and work format, I only have the basic saved fields on this card."
            )

        if self._contains_any(lowered, ("english", "англий")):
            english_level = display_english_level(getattr(candidate, "english_level", None))
            if english_level:
                return (
                    f"По {candidate_name} сохранен английский примерно на уровне {english_level}."
                    if ru
                    else f"For {candidate_name}, the saved English level is around {english_level}."
                )
            return (
                "По этой карточке уровень английского отдельно не сохранен."
                if ru
                else "I do not have a saved English level on this card."
            )

        if self._contains_any(lowered, ("domain", "product", "домен", "продукт")):
            domains = display_domains(getattr(candidate, "preferred_domains_json", None))
            if domains:
                return (
                    f"По доменам у {candidate_name}: " + ", ".join(domains[:5]) + "."
                    if ru
                    else f"For domains, {candidate_name} prefers: " + ", ".join(domains[:5]) + "."
                )
            return (
                "По этой карточке доменные предпочтения не указаны."
                if ru
                else "This card does not include explicit domain preferences."
            )

        if self._contains_any(lowered, ("process", "assessment", "take-home", "take home", "live coding", "процесс", "этап", "тестов", "таск", "лайвкод")):
            if assessments:
                return assessments
            return (
                "По assessment preferences у меня по этой карточке нет отдельных ограничений."
                if ru
                else "I do not have separate assessment-preference constraints on this card."
            )

        rag_answer = self._manager_review_dossier_answer(
            question_text=question_text,
            match=match,
            vacancy=vacancy,
            candidate=candidate,
            candidate_version=candidate_version,
        )
        if rag_answer:
            return rag_answer

        parts = []
        if summary_text:
            parts.append(
                f"Summary: {summary_text}" if not ru else f"Summary: {summary_text}"
            )
        elif years is not None:
            parts.append(f"{int(years)}+ лет опыта" if ru else f"{int(years)}+ years of experience")
        if skills:
            parts.append(
                ("Скиллы: " + ", ".join(skills))
                if ru
                else ("Skills: " + ", ".join(skills))
            )
        if preferences:
            parts.append(preferences.rstrip("."))
        if assessments:
            parts.append(assessments.rstrip("."))
        if fit_reason:
            parts.append(
                ("Почему показан: " + fit_reason)
                if ru
                else ("Why it was shown: " + fit_reason)
            )
        if gap_context:
            parts.append(
                ("Tradeoff: " + gap_context)
                if ru
                else ("Tradeoff: " + gap_context)
            )
        if not parts:
            return (
                "По этой карточке у меня сейчас только базовые поля без дополнительных деталей."
                if ru
                else "On this card, I currently only have the basic saved fields without extra details."
            )
        return " ".join(parts)

    @classmethod
    def _match_reason_text(cls, match) -> str | None:
        rationale = getattr(match, "rationale_json", None) or {}
        llm_rationale = cls._truncate_text(rationale.get("llm_rationale"), limit=180)
        if llm_rationale:
            return cls._normalize_sentence(llm_rationale)
        signals = cls._match_gapless_signals(match)
        if not signals:
            return None
        rendered = cls._join_with_and([cls._lower_lead(value) or "" for value in signals[:2] if cls._lower_lead(value)])
        if not rendered:
            return None
        return cls._normalize_sentence(f"It looks relevant because of {rendered}")

    @classmethod
    def _match_gapless_signals(cls, match) -> list[str]:
        rationale = getattr(match, "rationale_json", None) or {}
        result = []
        seen = set()
        for value in rationale.get("matched_signals") or []:
            cleaned = " ".join(str(value or "").split()).strip().rstrip(".")
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

    def _match_gap_context(self, match) -> str | None:
        gaps = self._match_gap_signals(match)
        if not gaps:
            return None
        supporting = self._match_gapless_signals(match)
        if supporting:
            support_text = self._join_with_and(supporting[:2])
            return self._normalize_sentence(f"{gaps[0]} The upside is {support_text}")
        return self._normalize_sentence(gaps[0])

    def _render_candidate_package_message(self, *, match, vacancy, slot_no: int | None = None) -> str:
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        if candidate is None:
            if slot_no is None:
                return "Candidate data is unavailable."
            return f"{slot_no}. Candidate data is unavailable."
        candidate_user = self.users.get_by_id(candidate.user_id)
        candidate_version = self.candidates.get_version_by_id(match.candidate_profile_version_id)
        summary = (candidate_version.summary_json or {}) if candidate_version else {}
        role_title = getattr(vacancy, "role_title", None) or "this role"
        candidate_name = (
            getattr(candidate_user, "display_name", None)
            or getattr(candidate_user, "username", None)
            or "a candidate"
        )
        approval_summary = self._truncate_text(summary.get("approval_summary_text"), limit=190)
        match_reason = self._match_reason_text(match)
        fit_band = fit_band_label(self._match_fit_band(match)) or "Relevant fit"
        location = getattr(candidate, "location_text", None)
        work_format = display_work_formats(candidate)
        english_level = display_english_level(getattr(candidate, "english_level", None))
        salary_label = self._candidate_salary_label(candidate)
        compensation_bits = []
        if salary_label:
            compensation_bits.append(f"salary expectation {salary_label}")
        if work_format:
            compensation_bits.append(f"prefers a {work_format} setup")
        if location:
            compensation_bits.append(f"based in {location}")
        if english_level:
            compensation_bits.append(f"English level {english_level}")

        paragraph_one_parts = [
            self._normalize_sentence(f"I found you {candidate_name} for the {role_title} role"),
            self._normalize_sentence(approval_summary),
            match_reason,
        ]
        paragraph_one = " ".join(part for part in paragraph_one_parts if part)

        paragraph_two_parts = []
        if compensation_bits:
            paragraph_two_parts.append(self._normalize_sentence(f"They want {self._join_with_and(compensation_bits)}"))
        paragraph_two_parts.append(self._normalize_sentence(f"This looks like a {fit_band.lower()}"))
        gap_signals = self._match_gap_signals(match)
        if gap_signals:
            paragraph_two_parts.append(
                self._normalize_sentence(f"Worth noting: {gap_signals[0]}")
            )
        paragraph_two_parts.append(self._normalize_sentence("Use Connect or Skip below"))

        fallback_message = "\n\n".join(
            paragraph
            for paragraph in [
                paragraph_one,
                " ".join(part for part in paragraph_two_parts if part),
            ]
            if paragraph
        )
        body = self.messaging.compose_match_card(
            audience="manager",
            role_title=role_title,
            candidate_name=candidate_name,
            candidate_summary=approval_summary,
            fit_reason=match_reason,
            compensation_details=self._join_with_and(compensation_bits) if compensation_bits else None,
            fit_band_label=fit_band,
            gap_context=self._match_gap_context(match),
            action_hint="Use Connect or Skip below.",
            fallback_message=fallback_message,
        )
        if slot_no is None:
            return body
        return f"{slot_no}.\n{body}"

    @staticmethod
    def _candidate_salary_label(candidate_profile) -> str | None:
        salary_min = getattr(candidate_profile, "salary_min", None)
        salary_max = getattr(candidate_profile, "salary_max", None)
        currency = getattr(candidate_profile, "salary_currency", None)
        period = getattr(candidate_profile, "salary_period", None)
        if salary_min is None and salary_max is None:
            return None
        if salary_min is not None and salary_max is not None:
            amount = f"{salary_min:.0f}-{salary_max:.0f}"
        else:
            amount = f"{(salary_min if salary_min is not None else salary_max):.0f}"
        if currency:
            amount = f"{amount} {currency}"
        if period:
            amount = f"{amount} per {period}"
        return amount

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
        summary = (vacancy_version.summary_json or {}) if vacancy_version else {}
        role_title = getattr(vacancy, "role_title", None) or "this role"
        vacancy_summary = self._truncate_text(
            summary.get("approval_summary_text") or getattr(vacancy, "project_description", None),
            limit=190,
        )
        project_description = self._truncate_text(getattr(vacancy, "project_description", None), limit=170)
        match_reason = self._match_reason_text(match)
        budget_label = self._vacancy_budget_label(vacancy)
        work_format = getattr(vacancy, "work_format", None)
        english_level = display_english_level(getattr(vacancy, "required_english_level", None))
        hiring_stages = self._effective_hiring_stages(vacancy)
        compensation_sentence = None
        if budget_label and work_format:
            compensation_sentence = self._normalize_sentence(
                f"The client is offering {budget_label} in a {work_format} setup"
            )
        elif budget_label:
            compensation_sentence = self._normalize_sentence(f"The client is offering {budget_label}")
        elif work_format:
            compensation_sentence = self._normalize_sentence(f"The role is set up as {work_format}")

        process_bits = []
        if english_level:
            process_bits.append(f"{english_level} English")
        if hiring_stages:
            process_bits.append(f"process: {', '.join(hiring_stages[:4])}")
        if getattr(vacancy, "has_take_home_task", None) is True:
            process_bits.append("a take-home task")
        if getattr(vacancy, "has_live_coding", None) is True:
            process_bits.append("live coding")

        paragraph_one_parts = [
            self._normalize_sentence(f"I found you a vacancy for {role_title}"),
            self._normalize_sentence(vacancy_summary or project_description),
            match_reason,
        ]
        paragraph_one = " ".join(part for part in paragraph_one_parts if part)

        paragraph_two_parts = []
        if compensation_sentence:
            paragraph_two_parts.append(compensation_sentence)
        if process_bits:
            paragraph_two_parts.append(
                self._normalize_sentence(f"Hiring details: {self._join_with_and(process_bits)}")
            )
        gap_signals = self._match_gap_signals(match)
        if gap_signals:
            paragraph_two_parts.append(self._normalize_sentence(f"Worth noting: {gap_signals[0]}"))
        if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED:
            paragraph_two_parts.append(
                self._normalize_sentence(
                    "The hiring manager already approved the connection, so tapping Connect will share contacts right away"
                )
            )
        else:
            paragraph_two_parts.append(self._normalize_sentence("Use Apply or Skip below"))

        fallback_message = "\n\n".join(
            paragraph
            for paragraph in [
                paragraph_one,
                " ".join(part for part in paragraph_two_parts if part),
            ]
            if paragraph
        )
        body = self.messaging.compose_match_card(
            audience="candidate",
            role_title=role_title,
            project_summary=vacancy_summary or project_description,
            fit_reason=match_reason,
            compensation_details=compensation_sentence.rstrip(".") if compensation_sentence else None,
            process_details=self._join_with_and(process_bits) if process_bits else None,
            gap_context=self._match_gap_context(match),
            action_hint=(
                "Use Connect or Skip below."
                if getattr(match, "status", None) == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED
                else "Use Apply or Skip below."
            ),
            fallback_message=fallback_message,
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
                f"I found a medium-fit candidate for {role_title}. "
                "The stronger options are exhausted for now, so I’m showing one current review card with the main gaps called out."
            )
        elif fit_band == "low":
            intro_text = (
                f"I found a low-fit candidate for {role_title}. "
                "Only review this if you want to stretch beyond the stronger options. The main gaps are called out in the card."
            )
        elif fit_band == "not_fit":
            intro_text = (
                f"I found a below-threshold candidate for {role_title}. "
                "This does not meet the normal fit bar, so review it only if you explicitly want a broad stretch option."
            )
        else:
            intro_text = (
                f"I found a strong-fit candidate for {role_title}. "
                "Review the current candidate card and use Connect or Skip below."
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
                    "I found a role worth reviewing for you. "
                    "Review the current vacancy card and use Apply or Skip below."
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
        manager_user_id = vacancy.manager_user_id
        current_match = self._current_manager_review_match_for_user(manager_user_id)
        if current_match is not None:
            current_vacancy = self.vacancies.get_by_id(current_match.vacancy_id)
            if force and trigger_type == "user_action" and current_vacancy is not None:
                self.notifications.create(
                    user_id=manager_user_id,
                    entity_type="vacancy",
                    entity_id=current_vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "message_entries": self._build_manager_batch_entries(
                            vacancy=current_vacancy,
                            batch=[current_match],
                        ),
                    },
                    allow_duplicate=True,
                )
                return {
                    "status": "dispatched",
                    "vacancy_id": str(vacancy_id),
                    "active_vacancy_id": str(current_vacancy.id),
                    "batch_count": 1,
                    "notified_count": 1,
                    "promoted_count": 0,
                    "fit_band": self._match_fit_band(current_match),
                    "notified": True,
                }
            return {
                "status": "already_presented",
                "vacancy_id": str(vacancy_id),
                "active_vacancy_id": str(getattr(current_match, "vacancy_id", vacancy_id)),
                "batch_count": 1,
                "promoted_count": 0,
                "notified": False,
            }

        if trigger_type == "user_action":
            shortlisted = self._collect_shortlisted_matches_for_manager(
                manager_user_id=manager_user_id,
                preferred_vacancy_id=vacancy_id,
            )
        else:
            if self._manager_batch_limit(vacancy.id) <= 0:
                if force:
                    self.notifications.create(
                        user_id=manager_user_id,
                        entity_type="vacancy",
                        entity_id=vacancy.id,
                        template_key="manager_pre_interview_review_ready",
                        payload_json={
                            "text": self._copy(
                                f"You already have {MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY} active candidate decisions "
                                "open on this vacancy. Review one of the current profiles first and I’ll send more as soon as there’s room."
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
            shortlisted = self._sort_matches_for_manager_review(
                self.matches.list_shortlisted_for_vacancy(
                    vacancy_id,
                    limit=MATCH_BATCH_SIZE * 6,
                )
            )

        if not shortlisted:
            return {
                "status": "empty",
                "vacancy_id": str(vacancy_id),
                "batch_count": 0,
                "promoted_count": 0,
                "notified": False,
            }

        match = shortlisted[0]
        selected_vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if selected_vacancy is None:
            return {
                "status": "empty",
                "vacancy_id": str(vacancy_id),
                "batch_count": 0,
                "promoted_count": 0,
                "notified": False,
            }
        self.state_service.transition(
            entity_type="match",
            entity=match,
            to_state=MATCH_STATUS_MANAGER_DECISION_PENDING,
            trigger_type=trigger_type,
            state_field="status",
            metadata_json={"vacancy_id": str(selected_vacancy.id), "presentation": "manager_pre_interview_review"},
        )
        self.notifications.create(
            user_id=manager_user_id,
            entity_type="vacancy",
            entity_id=selected_vacancy.id,
            template_key="manager_pre_interview_review_ready",
            payload_json={
                "message_entries": self._build_manager_batch_entries(vacancy=selected_vacancy, batch=[match]),
            },
            allow_duplicate=True,
        )
        return {
            "status": "dispatched",
            "vacancy_id": str(vacancy_id),
            "active_vacancy_id": str(selected_vacancy.id),
            "batch_count": 1,
            "notified_count": 1,
            "promoted_count": 1,
            "fit_band": self._match_fit_band(match),
            "notified": True,
        }

    def current_batch_size_for_manager(self, *, manager_user_id) -> int:
        return 1 if self._current_manager_review_match_for_user(manager_user_id) is not None else 0

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
                            "Review one of the current role decisions first and I’ll send more as soon as there’s room."
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
                limit=1,
            )
        )
        preexisting_count = len(current_batch)
        current_batch_ids = {match.id for match in current_batch}
        newly_promoted: list = []
        promoted_count = 0
        if len(current_batch) < 1:
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
                if len(current_batch) >= 1:
                    break

        if not current_batch:
            return {
                "status": "empty",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": 0,
                "promoted_count": promoted_count,
                "notified": False,
            }

        if promoted_count == 0 and preexisting_count > 0 and not (force and trigger_type == "user_action"):
            return {
                "status": "already_presented",
                "candidate_profile_id": str(candidate_profile_id),
                "batch_count": len(current_batch),
                "promoted_count": promoted_count,
                "notified": False,
            }

        notification_batch = current_batch if promoted_count == 0 else newly_promoted
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
        return len(self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=1))

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

        batch = self.matches.list_pre_interview_review_for_candidate(candidate.id, limit=1)
        match = self.matches.get_by_id(match_id) if match_id else None
        if match is not None:
            if not batch or batch[0].id != match.id:
                self.notifications.create(
                    user_id=user.id,
                    entity_type="candidate_profile",
                    entity_id=candidate.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            "That vacancy card is no longer active. Use the latest buttons under the current role card in chat and I’ll keep the queue moving from there."
                        ),
                    },
                    allow_duplicate=True,
                )
                return CandidateVacancyActionResult(status="invalid_match")
        elif not batch:
            self.notifications.create(
                user_id=user.id,
                entity_type="candidate_profile",
                entity_id=candidate.id,
                template_key="candidate_vacancy_review_ready",
                payload_json={
                    "text": self._copy(
                        "That vacancy card is no longer active. Use the latest buttons under the current role card in chat."
                    ),
                },
                allow_duplicate=True,
            )
            return CandidateVacancyActionResult(status="invalid_slot")

        if match is None:
            match = batch[0]
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        if vacancy is None:
            return None

        role_title = getattr(vacancy, "role_title", None) or "this role"
        manager_user = self.users.get_by_id(getattr(vacancy, "manager_user_id", None))
        candidate_user = self.users.get_by_id(getattr(candidate, "user_id", None))
        shared_contacts = False

        if action == "apply_to_vacancy":
            self._reset_candidate_skip_streak(candidate)
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
            skip_streak = self._record_candidate_skip(candidate)
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
            if self._should_prompt_skip_feedback(skip_streak):
                self.notifications.create(
                    user_id=user.id,
                    entity_type="candidate_profile",
                    entity_id=candidate.id,
                    template_key="candidate_vacancy_review_ready",
                    payload_json={
                        "text": self._copy(
                            "I’ve seen a few skips in a row. If these roles keep missing, tell me what’s off for you and I can update your matching preferences right here. "
                            "You can mention salary, format, location, English, domain, take-home, or live coding. "
                            "For example: remote only, from 5000, no live coding."
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
                        "That was the last role in your current review queue. I’ll send the next one as soon as matching produces it."
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
        current_match = self._current_manager_review_match_for_user(user.id)
        vacancy = self.vacancies.get_by_id(match.vacancy_id) if match is not None else None
        if vacancy is None and latest is not None:
            vacancy = self.vacancies.get_by_id(latest.vacancy_id)
        if vacancy is None:
            return None
        if vacancy.id not in vacancy_ids:
            return None

        batch = self.matches.list_pre_interview_review_for_vacancy(
            vacancy.id,
            limit=1,
        )
        if match is not None:
            if current_match is None or current_match.id != match.id or not batch or batch[0].id != match.id:
                self.notifications.create(
                    user_id=user.id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            "That candidate card is no longer active. Use the latest buttons under the current candidate card in chat and I’ll keep the queue moving from there."
                        ),
                    },
                    allow_duplicate=True,
                )
                return ManagerPreInterviewActionResult(status="invalid_match")
        elif not batch:
            self.notifications.create(
                user_id=user.id,
                entity_type="vacancy",
                entity_id=vacancy.id,
                template_key="manager_pre_interview_review_ready",
                payload_json={
                    "text": self._copy(
                        "That candidate card is no longer active. Use the latest buttons under the current candidate card in chat."
                    ),
                },
                allow_duplicate=True,
            )
            return ManagerPreInterviewActionResult(status="invalid_slot")

        if match is None:
            match = batch[0]
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        if candidate is None:
            return None

        candidate_name = self._candidate_label(candidate)
        previous_status = getattr(match, "status", None)
        role_title = getattr(vacancy, "role_title", None) or "this vacancy"
        candidate_user = self.users.get_by_id(candidate.user_id)
        shared_contacts = False

        if action == "interview_candidate":
            self._reset_manager_skip_streak(vacancy)
            if previous_status != MATCH_STATUS_CANDIDATE_APPLIED and self._manager_batch_limit(vacancy.id) <= 0:
                self.notifications.create(
                    user_id=user.id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            f"You already have {MAX_ACTIVE_INTERVIEW_CANDIDATES_PER_VACANCY} active candidate decisions "
                            "on this vacancy. Move one of the current profiles forward or close it, then I can approve another."
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
            skip_streak = self._record_manager_skip(vacancy)
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
            if self._should_prompt_skip_feedback(skip_streak):
                self.notifications.create(
                    user_id=user.id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="manager_pre_interview_review_ready",
                    payload_json={
                        "text": self._copy(
                            "I’ve seen a few skips in a row on this vacancy. Tell me what keeps missing and I can update the vacancy right here. "
                            "You can mention budget, English, format, city, process, project, or stack. "
                            "For example: budget 7000-9000, B2 English, no live coding."
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
                        "That was the last candidate in the current review queue. I will send the next one as soon as matching produces it."
                    ),
                },
                allow_duplicate=True,
            )
        return ManagerPreInterviewActionResult(status=status)
