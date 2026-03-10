from __future__ import annotations

from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.users import UsersRepository
from src.integrations.telegram_bot import TelegramBotClient
from src.notifications.rendering import (
    render_notification_messages,
    render_notification_reply_markup,
)


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
        return self.send_notification_by_id(payload["notification_id"])

    def send_notification_by_id(self, notification_id) -> dict:
        notification = self.notifications.get_by_id(notification_id)
        if notification is None:
            raise ValueError("Notification was not found.")
        if notification.status == "sent":
            return {"status": "already_sent", "notification_id": str(notification.id)}
        if notification.status == "cancelled":
            return {"status": "cancelled", "notification_id": str(notification.id)}
        if self.raw_messages.has_outbound_for_correlation(correlation_id=notification.id):
            self.notifications.mark_sent(notification)
            return {"status": "already_delivered", "notification_id": str(notification.id)}
        claimed_notification = self.notifications.claim_for_send(notification.id)
        if claimed_notification is None:
            latest = self.notifications.get_by_id(notification.id)
            if latest is None:
                raise ValueError("Notification was not found.")
            if latest.status == "sent":
                return {"status": "already_sent", "notification_id": str(latest.id)}
            if latest.status == "cancelled":
                return {"status": "cancelled", "notification_id": str(latest.id)}
            if self.raw_messages.has_outbound_for_correlation(correlation_id=latest.id):
                self.notifications.mark_sent(latest)
                return {"status": "already_delivered", "notification_id": str(latest.id)}
            return {
                "status": "already_claimed",
                "notification_id": str(latest.id),
                "notification_status": latest.status,
            }
        return self.send_notification(claimed_notification)

    def send_notification(self, notification) -> dict:
        if notification is None:
            raise ValueError("Notification was not found.")
        try:
            user = self.users.get_by_id(notification.user_id)
            if user is None or not user.telegram_chat_id:
                raise ValueError("Notification user or telegram_chat_id is not available.")
            if self.raw_messages.has_outbound_for_correlation(correlation_id=notification.id):
                self.notifications.mark_sent(notification)
                return {
                    "status": "already_delivered",
                    "notification_id": str(notification.id),
                }

            messages = render_notification_messages(
                template_key=notification.template_key,
                payload=notification.payload_json or {},
            )
            reply_markup = render_notification_reply_markup(
                template_key=notification.template_key,
                payload=notification.payload_json or {},
            )
            telegram_results = []
            for index, text in enumerate(messages):
                telegram_result = self.telegram.send_text_message(
                    chat_id=user.telegram_chat_id,
                    text=text,
                    reply_markup=reply_markup if index == len(messages) - 1 else None,
                )
                telegram_results.append(telegram_result)
                self.raw_messages.create(
                    user_id=user.id,
                    telegram_update_id=None,
                    telegram_message_id=telegram_result.get("message_id"),
                    telegram_chat_id=user.telegram_chat_id,
                    direction="outbound",
                    content_type="text",
                    payload_json=telegram_result,
                    text_content=text,
                    correlation_id=notification.id,
                )
            self.notifications.mark_sent(notification)
            return {
                "status": "sent",
                "notification_id": str(notification.id),
                "telegram_message_id": telegram_results[-1].get("message_id") if telegram_results else None,
                "message_count": len(telegram_results),
            }
        except Exception as exc:
            self.notifications.mark_failed(notification, error_message=str(exc))
            raise

    def deliver_notification_ids(self, notification_ids: list[str]) -> list[dict]:
        results: list[dict] = []
        for notification_id in notification_ids:
            results.append(self.send_notification_by_id(notification_id))
        return results
