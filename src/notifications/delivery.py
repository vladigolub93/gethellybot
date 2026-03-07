from __future__ import annotations

from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.users import UsersRepository
from src.integrations.telegram_bot import TelegramBotClient
from src.notifications.rendering import render_notification_text


class NotificationDeliveryService:
    def __init__(self, session):
        self.session = session
        self.notifications = NotificationsRepository(session)
        self.users = UsersRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.telegram = TelegramBotClient()

    def process_job(self, job) -> dict:
        if job.job_type != "notification_send_telegram_v1":
            raise ValueError(f"Unsupported notification job type: {job.job_type}")

        payload = job.payload_json or {}
        notification = self.notifications.get_by_id(payload["notification_id"])
        if notification is None:
            raise ValueError("Notification was not found.")
        if notification.status == "sent":
            return {"status": "already_sent", "notification_id": str(notification.id)}
        if notification.status == "cancelled":
            return {"status": "cancelled", "notification_id": str(notification.id)}
        try:
            user = self.users.get_by_id(notification.user_id)
            if user is None or not user.telegram_chat_id:
                raise ValueError("Notification user or telegram_chat_id is not available.")

            text = render_notification_text(
                template_key=notification.template_key,
                payload=notification.payload_json or {},
            )
            telegram_result = self.telegram.send_text_message(
                chat_id=user.telegram_chat_id,
                text=text,
            )
            self.raw_messages.create(
                user_id=user.id,
                telegram_update_id=None,
                telegram_message_id=telegram_result.get("message_id"),
                telegram_chat_id=user.telegram_chat_id,
                direction="outbound",
                content_type="text",
                payload_json=telegram_result,
                text_content=text,
            )
            self.notifications.mark_sent(notification)
            return {
                "status": "sent",
                "notification_id": str(notification.id),
                "telegram_message_id": telegram_result.get("message_id"),
            }
        except Exception as exc:
            self.notifications.mark_failed(notification, error_message=str(exc))
            raise
