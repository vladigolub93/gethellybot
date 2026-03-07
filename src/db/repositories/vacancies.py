from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models.vacancies import Vacancy, VacancyVersion


INCOMPLETE_VACANCY_STATES = (
    "NEW",
    "INTAKE_PENDING",
    "JD_PROCESSING",
    "CLARIFICATION_QA",
)


class VacanciesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_latest_incomplete_by_manager_user_id(self, manager_user_id) -> Optional[Vacancy]:
        stmt = (
            select(Vacancy)
            .where(
                Vacancy.manager_user_id == manager_user_id,
                Vacancy.deleted_at.is_(None),
                Vacancy.state.in_(INCOMPLETE_VACANCY_STATES),
            )
            .order_by(Vacancy.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, vacancy_id) -> Optional[Vacancy]:
        stmt = select(Vacancy).where(Vacancy.id == vacancy_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_open_vacancies(self) -> list[Vacancy]:
        stmt = select(Vacancy).where(
            Vacancy.state == "OPEN",
            Vacancy.deleted_at.is_(None),
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_version_by_id(self, version_id) -> Optional[VacancyVersion]:
        stmt = select(VacancyVersion).where(VacancyVersion.id == version_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, *, manager_user_id, state: str) -> Vacancy:
        row = Vacancy(manager_user_id=manager_user_id, state=state)
        self.session.add(row)
        self.session.flush()
        return row

    def next_version_no(self, vacancy_id) -> int:
        stmt = select(func.coalesce(func.max(VacancyVersion.version_no), 0)).where(
            VacancyVersion.vacancy_id == vacancy_id
        )
        current_max = self.session.execute(stmt).scalar_one()
        return int(current_max) + 1

    def create_version(
        self,
        *,
        vacancy_id,
        version_no: int,
        source_type: str,
        source_file_id=None,
        source_raw_message_id=None,
        extracted_text=None,
        transcript_text=None,
        summary_json=None,
        normalization_json=None,
        inconsistency_json=None,
        prompt_version=None,
        model_name=None,
    ) -> VacancyVersion:
        row = VacancyVersion(
            vacancy_id=vacancy_id,
            version_no=version_no,
            source_type=source_type,
            source_file_id=source_file_id,
            source_raw_message_id=source_raw_message_id,
            extracted_text=extracted_text,
            transcript_text=transcript_text,
            summary_json=summary_json,
            normalization_json=normalization_json,
            inconsistency_json=inconsistency_json,
            prompt_version=prompt_version,
            model_name=model_name,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def set_current_version(self, vacancy: Vacancy, version_id) -> Vacancy:
        vacancy.current_version_id = version_id
        self.session.flush()
        return vacancy

    def get_current_version(self, vacancy: Vacancy) -> Optional[VacancyVersion]:
        if vacancy.current_version_id is None:
            return None
        return self.get_version_by_id(vacancy.current_version_id)

    def update_version_analysis(
        self,
        version: VacancyVersion,
        *,
        summary_json=None,
        normalization_json=None,
        inconsistency_json=None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> VacancyVersion:
        if summary_json is not None:
            version.summary_json = summary_json
        if normalization_json is not None:
            version.normalization_json = normalization_json
        if inconsistency_json is not None:
            version.inconsistency_json = inconsistency_json
        if prompt_version is not None:
            version.prompt_version = prompt_version
        if model_name is not None:
            version.model_name = model_name
        self.session.flush()
        return version

    def update_questions_context(self, vacancy: Vacancy, questions_context_json: dict) -> Vacancy:
        vacancy.questions_context_json = questions_context_json
        self.session.flush()
        return vacancy

    def update_clarifications(
        self,
        vacancy: Vacancy,
        *,
        role_title=None,
        seniority_normalized=None,
        budget_min=None,
        budget_max=None,
        budget_currency=None,
        budget_period=None,
        countries_allowed_json=None,
        work_format=None,
        team_size=None,
        project_description=None,
        primary_tech_stack_json=None,
    ) -> Vacancy:
        if role_title is not None:
            vacancy.role_title = role_title
        if seniority_normalized is not None:
            vacancy.seniority_normalized = seniority_normalized
        if budget_min is not None:
            vacancy.budget_min = budget_min
        if budget_max is not None:
            vacancy.budget_max = budget_max
        if budget_currency is not None:
            vacancy.budget_currency = budget_currency
        if budget_period is not None:
            vacancy.budget_period = budget_period
        if countries_allowed_json is not None:
            vacancy.countries_allowed_json = countries_allowed_json
        if work_format is not None:
            vacancy.work_format = work_format
        if team_size is not None:
            vacancy.team_size = team_size
        if project_description is not None:
            vacancy.project_description = project_description
        if primary_tech_stack_json is not None:
            vacancy.primary_tech_stack_json = primary_tech_stack_json
        self.session.flush()
        return vacancy

    def mark_open(self, vacancy: Vacancy) -> Vacancy:
        vacancy.opened_at = datetime.now(timezone.utc)
        self.session.flush()
        return vacancy
