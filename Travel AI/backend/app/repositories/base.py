from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Small reusable foundation for model-specific repositories."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    def get(self, identifier: object) -> ModelT | None:
        return self.session.get(self.model, identifier)
