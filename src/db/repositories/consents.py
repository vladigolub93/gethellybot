from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models.core import UserConsent


class UserConsentsRepository:
    def __init__(self, session: Session):
        self.session = session

    def latest_for_user(self, user_id, consent_type: str):
        stmt = (
            select(UserConsent)
            .where(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
            )
            .order_by(desc(UserConsent.granted_at))
        )
        return self.session.execute(stmt).scalars().first()

    def has_granted(self, user_id, consent_type: str) -> bool:
        latest = self.latest_for_user(user_id, consent_type)
        return bool(latest and latest.granted)

    def grant(self, user_id, consent_type: str, source_raw_message_id=None, policy_version="v1"):
        consent = UserConsent(
            user_id=user_id,
            consent_type=consent_type,
            granted=True,
            policy_version=policy_version,
            source_raw_message_id=source_raw_message_id,
            granted_at=datetime.now(timezone.utc),
        )
        self.session.add(consent)
        self.session.flush()
        return consent

