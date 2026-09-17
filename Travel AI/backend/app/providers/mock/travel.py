"""Deterministic mock flight and hotel providers for optimization and evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from app.providers.base import FlightProvider, HotelProvider
from app.providers.mock.catalog import normalize_destination
from app.providers.models import (
    FlightSearchRequest,
    FlightSearchResult,
    HotelSearchRequest,
    HotelSearchResult,
)

# Destination-centered coordinates keep hotel ranking deterministic per city.
_DEST_COORDS: Dict[str, Tuple[float, float]] = {
    "hanoi": (21.0285, 105.8542),
    "da nang": (16.0544, 108.2475),
    "hoi an": (15.8801, 108.3380),
    "da lat": (11.9404, 108.4583),
    "phu quoc": (10.2899, 103.9840),
    "ho chi minh city": (10.7769, 106.7009),
    "nha trang": (12.2388, 109.1967),
    "ha long": (20.9101, 107.1839),
}


class MockHotelProvider(HotelProvider):
    """Three ranked hotels per destination so the optimizer can explain A→B swaps."""

    def search_hotels(self, request: HotelSearchRequest) -> List[HotelSearchResult]:
        destination = request.destination
        key = normalize_destination(destination) or destination.casefold()
        lat, lng = _DEST_COORDS.get(key, (16.0544, 108.2475))
        slug = key.replace(" ", "-")
        return [
            HotelSearchResult(
                id=f"hotel-a-{slug}",
                name=f"Hotel A Premium {destination}",
                destination=destination,
                address=f"Central Beach Road, {destination}",
                latitude=lat,
                longitude=lng,
                rating=4.6,
                nightly_price=2_200_000,
                currency=request.currency,
                amenities=["beach", "pool", "breakfast"],
            ),
            HotelSearchResult(
                id=f"hotel-b-{slug}",
                name=f"Hotel B Near Center {destination}",
                destination=destination,
                address=f"Near Center, {destination}",
                latitude=lat + 0.002,
                longitude=lng - 0.003,
                rating=4.4,
                nightly_price=1_700_000,
                currency=request.currency,
                amenities=["wifi", "breakfast"],
            ),
            HotelSearchResult(
                id=f"hotel-c-{slug}",
                name=f"Hotel C Budget {destination}",
                destination=destination,
                address=f"Inland Road, {destination}",
                latitude=lat + 0.015,
                longitude=lng - 0.020,
                rating=3.9,
                nightly_price=900_000,
                currency=request.currency,
                amenities=["wifi"],
            ),
        ]


class MockFlightProvider(FlightProvider):
    def search_flights(self, request: FlightSearchRequest) -> List[FlightSearchResult]:
        departure = datetime.combine(request.departure_date, datetime.min.time()).replace(hour=8)
        return [
            FlightSearchResult(
                id="flight-premium",
                airline="Vietnam Airlines",
                flight_number="VN123",
                departure_at=departure,
                arrival_at=departure.replace(hour=9, minute=30),
                origin=request.origin,
                destination=request.destination,
                price=2_100_000,
                currency=request.currency,
                stops=0,
            ),
            FlightSearchResult(
                id="flight-value",
                airline="VietJet",
                flight_number="VJ450",
                departure_at=departure.replace(hour=10),
                arrival_at=departure.replace(hour=11, minute=20),
                origin=request.origin,
                destination=request.destination,
                price=1_450_000,
                currency=request.currency,
                stops=0,
            ),
        ]
