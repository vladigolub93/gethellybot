from sqlalchemy.orm import Session

from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.jobs.queue import JobMessage, QueueClient


class DatabaseQueueClient(QueueClient):
    def __init__(self, session: Session):
        self.repo = JobExecutionLogsRepository(session)

    def enqueue(self, message: JobMessage) -> None:
        self.repo.enqueue(
            job_type=message.job_type,
            idempotency_key=message.idempotency_key,
            payload_json=message.payload,
            entity_type=message.entity_type or None,
            entity_id=message.entity_id,
        )
