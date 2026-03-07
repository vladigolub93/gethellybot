from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.db.models.core import Notification


class NotificationsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, notification_id) -> Optional[Notification]:
        stmt = select(Notification).where(Notification.id == notification_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        user_id,
        entity_type: str,
        entity_id,
        template_key: str,
        payload_json: dict,
        channel: str = "telegram",
        status: str = "pending",
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            channel=channel,
            template_key=template_key,
            payload_json=payload_json,
            status=status,
        )
        self.session.add(notification)
        self.session.flush()
        return notification

    def list_pending_dispatchable(self, *, limit: int = 20) -> list[Notification]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Notification)
            .where(
                Notification.status == "pending",
                or_(Notification.send_after.is_(None), Notification.send_after <= now),
            )
            .order_by(Notification.created_at.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def mark_queued(self, notification: Notification) -> Notification:
        notification.status = "queued"
        self.session.flush()
        return notification

    def mark_sent(self, notification: Notification) -> Notification:
        notification.status = "sent"
        notification.sent_at = datetime.now(timezone.utc)
        notification.last_error = None
        self.session.flush()
        return notification

    def mark_failed(self, notification: Notification, *, error_message: str) -> Notification:
        notification.status = "failed"
        notification.failure_count = (notification.failure_count or 0) + 1
        notification.last_error = error_message[:4000]
        self.session.flush()
        return notification
