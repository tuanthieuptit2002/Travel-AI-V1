"""In-memory trip persistence for the pre-auth API phase."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Lock
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4


@dataclass
class StoredTrip:
    id: UUID
    user_id: Optional[UUID]
    destination: str
    origin: Optional[str]
    start_date: date
    end_date: date
    travelers: int
    budget: Optional[Decimal]
    currency: str
    status: str
    summary: Optional[str]
    estimated_total_cost: Optional[Decimal]
    itinerary: list
    warnings: list
    recommendations: list
    weather: list = field(default_factory=list)
    weather_notes: list = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TripStore(Protocol):
    def create(self, trip: StoredTrip) -> StoredTrip:
        ...

    def get(self, trip_id: UUID) -> Optional[StoredTrip]:
        ...

    def list(self, user_id: Optional[UUID] = None) -> List[StoredTrip]:
        ...


class InMemoryTripStore:
    """Thread-safe process-local store used until auth + SQL persistence land."""

    def __init__(self) -> None:
        self._trips: Dict[UUID, StoredTrip] = {}
        self._lock = Lock()

    def create(self, trip: StoredTrip) -> StoredTrip:
        with self._lock:
            stored = deepcopy(trip)
            if stored.id is None:
                stored.id = uuid4()
            self._trips[stored.id] = stored
            return deepcopy(stored)

    def get(self, trip_id: UUID) -> Optional[StoredTrip]:
        with self._lock:
            trip = self._trips.get(trip_id)
            return deepcopy(trip) if trip else None

    def list(self, user_id: Optional[UUID] = None) -> List[StoredTrip]:
        with self._lock:
            trips = list(self._trips.values())
            if user_id is not None:
                trips = [trip for trip in trips if trip.user_id == user_id]
            trips.sort(key=lambda item: item.created_at, reverse=True)
            return [deepcopy(trip) for trip in trips]

    def clear(self) -> None:
        with self._lock:
            self._trips.clear()


_store = InMemoryTripStore()


def get_trip_store() -> InMemoryTripStore:
    return _store
