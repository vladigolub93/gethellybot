from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.db.models.core import Notification


class NotificationsRepository:
    CANCELLABLE_STATUSES = ("pending", "queued")

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

    def list_pending_dispatchable_for_user(self, *, user_id, limit: int = 20) -> list[Notification]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == user_id,
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

    def mark_cancelled(self, notification: Notification, *, reason: Optional[str] = None) -> Notification:
        notification.status = "cancelled"
        if reason:
            notification.last_error = reason[:4000]
        self.session.flush()
        return notification

    def cancel_for_entities(
        self,
        *,
        refs: list[tuple[str, object]],
        exclude_template_keys: Optional[list[str]] = None,
    ) -> int:
        if not refs:
            return 0
        conditions = [
            and_(Notification.entity_type == entity_type, Notification.entity_id == entity_id)
            for entity_type, entity_id in refs
        ]
        stmt = select(Notification).where(
            Notification.status.in_(self.CANCELLABLE_STATUSES),
            or_(*conditions),
        )
        if exclude_template_keys:
            stmt = stmt.where(Notification.template_key.not_in(exclude_template_keys))

        rows = list(self.session.execute(stmt).scalars().all())
        for row in rows:
            row.status = "cancelled"
            row.last_error = "cancelled_by_cleanup_job"
        self.session.flush()
        return len(rows)
