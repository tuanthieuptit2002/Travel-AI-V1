import uuid
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.travel import Place, TripActivity, TripDay
from app.repositories.trip import TripRepository


@dataclass(frozen=True)
class TripBudgetSummary:
    trip_id: uuid.UUID
    total_budget: Optional[Decimal]
    scheduled_cost: Decimal
    remaining_budget: Optional[Decimal]
    currency: str


@dataclass(frozen=True)
class SaveTripActivityCommand:
    trip_day_id: uuid.UUID
    activity_type: str
    place_id: Optional[uuid.UUID] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    notes: Optional[str] = None
    estimated_cost: Optional[Decimal] = None
    order_index: Optional[int] = None


class TripService:
    """The only database mutation/read boundary exposed to agent tools."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.trips = TripRepository(session)

    def get_budget(self, trip_id: uuid.UUID) -> Optional[TripBudgetSummary]:
        trip = self.trips.get_by_id(trip_id)
        if trip is None:
            return None
        scheduled_cost = self.session.scalar(
            select(func.coalesce(func.sum(TripActivity.estimated_cost), 0))
            .join(TripDay)
            .where(TripDay.trip_id == trip_id)
        )
        scheduled = Decimal(scheduled_cost or 0)
        remaining = trip.budget - scheduled if trip.budget is not None else None
        return TripBudgetSummary(
            trip_id=trip.id,
            total_budget=trip.budget,
            scheduled_cost=scheduled,
            remaining_budget=remaining,
            currency=trip.currency,
        )

    def save_trip_activity(self, command: SaveTripActivityCommand) -> TripActivity:
        trip_day = self.session.get(TripDay, command.trip_day_id)
        if trip_day is None:
            raise ValueError("Trip day was not found.")
        if command.place_id is not None and self.session.get(Place, command.place_id) is None:
            raise ValueError("Place was not found.")
        if command.start_time and command.end_time and command.end_time <= command.start_time:
            raise ValueError("End time must be after start time.")

        order_index = command.order_index
        if order_index is None:
            current_max = self.session.scalar(
                select(func.max(TripActivity.order_index)).where(TripActivity.trip_day_id == command.trip_day_id)
            )
            order_index = int(current_max or 0) + 1

        activity = TripActivity(
            trip_day_id=command.trip_day_id,
            place_id=command.place_id,
            start_time=command.start_time,
            end_time=command.end_time,
            activity_type=command.activity_type.strip(),
            notes=command.notes.strip() if command.notes else None,
            estimated_cost=command.estimated_cost,
            order_index=order_index,
        )
        self.session.add(activity)
        self.session.flush()
        return activity
