"""Data-access layer; repositories keep persistence details out of services."""

from app.repositories.user import UserRepository

__all__ = ["UserRepository"]
