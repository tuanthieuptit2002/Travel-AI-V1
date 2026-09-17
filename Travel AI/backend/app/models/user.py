from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.travel import Trip


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    preference: Mapped[Optional["UserPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    """SQL persistence for structured UserMemory fields (not conversation logs)."""

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    preferred_destinations: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    preferred_activities: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    food_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    dislikes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    preferred_trip_pace: Mapped[Optional[str]] = mapped_column(String(50))
    budget_level: Mapped[Optional[str]] = mapped_column(String(50))
    accommodation_preference: Mapped[Optional[str]] = mapped_column(String(50))
    transportation_preference: Mapped[Optional[str]] = mapped_column(String(50))

    user: Mapped[User] = relationship(back_populates="preference")
