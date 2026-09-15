from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.config import get_settings

if TYPE_CHECKING:
    from app.models.user import User


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    origin: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    travelers: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="VND")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="trips")
    days: Mapped[list["TripDay"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripDay.day_number"
    )
    flights: Mapped[list["Flight"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class TripDay(Base):
    __tablename__ = "trip_days"
    __table_args__ = (
        UniqueConstraint("trip_id", "date", name="uq_trip_days_trip_date"),
        UniqueConstraint("trip_id", "day_number", name="uq_trip_days_trip_day_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="days")
    activities: Mapped[list["TripActivity"]] = relationship(
        back_populates="trip_day", cascade="all, delete-orphan", order_by="TripActivity.order_index"
    )


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("provider", "provider_place_id", name="uq_places_provider_place_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    address: Mapped[Optional[str]] = mapped_column(Text)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(2, 1))
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    activities: Mapped[list["TripActivity"]] = relationship(back_populates="place")
    restaurant: Mapped[Optional["Restaurant"]] = relationship(back_populates="place", cascade="all, delete-orphan", uselist=False)
    hotel: Mapped[Optional["Hotel"]] = relationship(back_populates="place", cascade="all, delete-orphan", uselist=False)


class TripActivity(Base):
    __tablename__ = "trip_activities"
    __table_args__ = (UniqueConstraint("trip_day_id", "order_index", name="uq_trip_activities_day_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_days.id", ondelete="CASCADE"), nullable=False
    )
    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL"))
    start_time: Mapped[Optional[time]] = mapped_column(Time)
    end_time: Mapped[Optional[time]] = mapped_column(Time)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    trip_day: Mapped[TripDay] = relationship(back_populates="activities")
    place: Mapped[Optional[Place]] = relationship(back_populates="activities")


class Restaurant(Base):
    __tablename__ = "restaurants"

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), primary_key=True
    )
    cuisine_types: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    price_level: Mapped[Optional[str]] = mapped_column(String(50))

    place: Mapped[Place] = relationship(back_populates="restaurant")


class Hotel(Base):
    __tablename__ = "hotels"

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), primary_key=True
    )
    nightly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    amenities: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    place: Mapped[Place] = relationship(back_populates="hotel")


class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_flight_id: Mapped[Optional[str]] = mapped_column(String(255))
    airline: Mapped[Optional[str]] = mapped_column(String(100))
    flight_number: Mapped[Optional[str]] = mapped_column(String(50))
    departure_airport: Mapped[str] = mapped_column(String(10), nullable=False)
    arrival_airport: Mapped[str] = mapped_column(String(10), nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="VND")

    trip: Mapped[Optional[Trip]] = relationship(back_populates="flights")


class TravelKnowledgeDocument(Base):
    __tablename__ = "travel_knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(1000))
    destination: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(get_settings().embedding_dimensions))
