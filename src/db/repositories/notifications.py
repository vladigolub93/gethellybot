from sqlalchemy.orm import Session

from src.db.models.core import Notification


class NotificationsRepository:
    def __init__(self, session: Session):
        self.session = session

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

