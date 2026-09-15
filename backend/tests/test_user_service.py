from unittest.mock import MagicMock

from app.services.user_service import UserService


def test_create_user_normalizes_email_and_name() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    service = UserService(session)

    user = service.create_user(email="  TRAVELER@EXAMPLE.COM ", name="  Linh  ")

    assert user.email == "traveler@example.com"
    assert user.name == "Linh"
    session.add.assert_called_once_with(user)
    session.flush.assert_called_once()


def test_create_user_rejects_duplicate_email() -> None:
    session = MagicMock()
    session.scalar.return_value = object()
    service = UserService(session)

    try:
        service.create_user(email="traveler@example.com", name="Linh")
    except ValueError as error:
        assert str(error) == "A user with this email already exists."
    else:
        raise AssertionError("Expected duplicate user creation to fail")
