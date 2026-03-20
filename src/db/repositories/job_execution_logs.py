from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import not_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models.core import JobExecutionLog


class JobExecutionLogsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, job_id) -> Optional[JobExecutionLog]:
        stmt = select(JobExecutionLog).where(JobExecutionLog.id == job_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_candidate_manual_request_jobs(
        self,
        *,
        candidate_profile_id: str,
        request_id: str,
    ) -> list[JobExecutionLog]:
        stmt = (
            select(JobExecutionLog)
            .where(
                JobExecutionLog.job_type == "matching_run_for_vacancy_v1",
                JobExecutionLog.payload_json["trigger_type"].astext == "candidate_manual_request",
                JobExecutionLog.payload_json["trigger_candidate_profile_id"].astext == str(candidate_profile_id),
                JobExecutionLog.payload_json["candidate_manual_request_id"].astext == str(request_id),
            )
            .order_by(JobExecutionLog.queued_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_idempotency_key(self, *, job_type: str, idempotency_key: str) -> Optional[JobExecutionLog]:
        stmt = select(JobExecutionLog).where(
            JobExecutionLog.job_type == job_type,
            JobExecutionLog.idempotency_key == idempotency_key,
            JobExecutionLog.attempt_no == 1,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def enqueue(
        self,
        *,
        job_type: str,
        idempotency_key: str,
        payload_json: dict,
        entity_type: Optional[str] = None,
        entity_id=None,
    ) -> JobExecutionLog:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            insert_stmt = (
                pg_insert(JobExecutionLog)
                .values(
                    job_type=job_type,
                    idempotency_key=idempotency_key,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status="queued",
                    attempt_no=1,
                    payload_json=payload_json,
                )
                .on_conflict_do_nothing(
                    index_elements=["job_type", "idempotency_key", "attempt_no"]
                )
                .returning(JobExecutionLog.id)
            )
            inserted_id = self.session.execute(insert_stmt).scalar_one_or_none()
            if inserted_id is not None:
                return self.get_by_id(inserted_id)

        existing = self.get_by_idempotency_key(
            job_type=job_type,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing

        row = JobExecutionLog(
            job_type=job_type,
            idempotency_key=idempotency_key,
            entity_type=entity_type,
            entity_id=entity_id,
            status="queued",
            payload_json=payload_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def claim_by_id_if_queued(self, job_id) -> Optional[JobExecutionLog]:
        stmt = (
            select(JobExecutionLog)
            .where(
                JobExecutionLog.id == job_id,
                JobExecutionLog.status == "queued",
            )
            .with_for_update(skip_locked=True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def claim_next_queued(self) -> Optional[JobExecutionLog]:
        stmt = (
            select(JobExecutionLog)
            .where(JobExecutionLog.status == "queued")
            .order_by(JobExecutionLog.queued_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def claim_next_queued_non_notification(self) -> Optional[JobExecutionLog]:
        stmt = (
            select(JobExecutionLog)
            .where(
                JobExecutionLog.status == "queued",
                not_(JobExecutionLog.job_type.like("notification_%")),
            )
            .order_by(JobExecutionLog.queued_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def mark_started(self, job: JobExecutionLog) -> JobExecutionLog:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        self.session.flush()
        return job

    def mark_completed(self, job: JobExecutionLog, *, result_json: Optional[dict] = None) -> JobExecutionLog:
        job.status = "completed"
        job.result_json = result_json
        job.finished_at = datetime.now(timezone.utc)
        self.session.flush()
        return job

    def mark_failed(self, job: JobExecutionLog, *, error_message: str) -> JobExecutionLog:
        job.status = "failed"
        job.last_error = error_message[:4000]
        job.finished_at = datetime.now(timezone.utc)
        self.session.flush()
        return job
