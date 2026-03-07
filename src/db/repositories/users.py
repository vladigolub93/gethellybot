from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.core import User


class UsersRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_telegram_user_id(self, telegram_user_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id):
        stmt = select(User).where(User.id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create_or_update_from_telegram(
        self,
        telegram_user_id: int,
        telegram_chat_id: Optional[int],
        display_name: Optional[str],
        username: Optional[str],
        language_code: Optional[str],
    ) -> User:
        user = self.get_by_telegram_user_id(telegram_user_id)
        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                display_name=display_name,
                username=username,
                language_code=language_code,
            )
            self.session.add(user)
            self.session.flush()
            return user

        user.telegram_chat_id = telegram_chat_id or user.telegram_chat_id
        user.display_name = display_name or user.display_name
        user.username = username or user.username
        user.language_code = language_code or user.language_code
        self.session.flush()
        return user

    def attach_contact(self, user: User, phone_number: Optional[str]) -> User:
        user.phone_number = phone_number or user.phone_number
        self.session.flush()
        return user

    def set_role(self, user: User, role: str) -> User:
        if role == "candidate":
            user.is_candidate = True
            user.is_hiring_manager = False
        elif role == "hiring_manager":
            user.is_candidate = False
            user.is_hiring_manager = True
        else:
            raise ValueError(f"Unsupported role: {role}")
        self.session.flush()
        return user
