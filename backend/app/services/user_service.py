from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user import UserRepository


class UserService:
    """User creation rules, kept separate from future HTTP endpoints."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    def create_user(self, *, email: str, name: str) -> User:
        normalized_email = email.strip().lower()
        if self.users.get_by_email(normalized_email) is not None:
            raise ValueError("A user with this email already exists.")

        user = self.users.add(User(email=normalized_email, name=name.strip()))
        self.session.flush()
        return user
