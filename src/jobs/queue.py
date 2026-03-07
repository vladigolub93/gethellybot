from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class JobMessage:
    job_type: str
    payload: Dict[str, Any]
    idempotency_key: str


class QueueClient(Protocol):
    def enqueue(self, message: JobMessage) -> None:
        """Enqueue a message for background processing."""

