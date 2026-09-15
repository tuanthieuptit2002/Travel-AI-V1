"""Call several TripMind tools directly, without an LLM or external API credentials.

Run from backend/:
    PYTHONPATH=. python scripts/test_tools.py
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.providers.base import FlightProvider, HotelProvider
from app.providers.mock import MockPlacesProvider, MockRouteProvider, MockWeatherProvider
from app.providers.models import (
    FlightSearchRequest,
    FlightSearchResult,
    HotelSearchRequest,
    HotelSearchResult,
)
from app.services.trip_service import TripBudgetSummary
from app.tools import ToolDependencies, create_agent_tools


class DemoFlightProvider(FlightProvider):
    def search_flights(self, request: FlightSearchRequest) -> list[FlightSearchResult]:
        return [
            FlightSearchResult(
                id="demo-flight-1",
                airline="Vietnam Airlines",
                flight_number="VN154",
                departure_at=datetime(2026, 10, 12, 7, 30),
                arrival_at=datetime(2026, 10, 12, 9, 0),
                origin=request.origin,
                destination=request.destination,
                price=1650000,
                currency=request.currency,
                stops=0,
            )
        ]


class DemoHotelProvider(HotelProvider):
    def search_hotels(self, request: HotelSearchRequest) -> list[HotelSearchResult]:
        return [
            HotelSearchResult(
                id="demo-hotel-1",
                name="Demo Beach Hotel",
                destination=request.destination,
                address="100 Coastal Avenue",
                latitude=16.06,
                longitude=108.25,
                rating=4.4,
                nightly_price=980000,
                currency=request.currency,
                amenities=["wifi", "pool"],
            )
        ]


class DemoTripService:
    def __init__(self) -> None:
        self.trip_id = uuid4()
        self.trip_day_id = uuid4()

    def get_budget(self, trip_id: object) -> TripBudgetSummary | None:
        if trip_id != self.trip_id:
            return None
        return TripBudgetSummary(
            trip_id=self.trip_id,
            total_budget=Decimal("10000000"),
            scheduled_cost=Decimal("1500000"),
            remaining_budget=Decimal("8500000"),
            currency="VND",
        )

    def save_trip_activity(self, command: object) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid4(),
            trip_day_id=getattr(command, "trip_day_id"),
            place_id=None,
            activity_type=getattr(command, "activity_type"),
            order_index=1,
            estimated_cost=getattr(command, "estimated_cost", None),
        )


def main() -> None:
    trip_service = DemoTripService()
    dependencies = ToolDependencies(
        places=MockPlacesProvider(),
        weather=MockWeatherProvider(),
        routes=MockRouteProvider(),
        flights=DemoFlightProvider(),
        hotels=DemoHotelProvider(),
        trip_service=trip_service,  # type: ignore[arg-type]
    )
    tools = {tool.name: tool for tool in create_agent_tools(dependencies)}

    calls = {
        "search_places": {
            "destination": "Da Nang",
            "query": "beach",
            "latitude": 16.0544,
            "longitude": 108.2467,
            "radius_km": 5,
        },
        "get_place_details": {"place_id": "vn-danang-my-khe"},
        "search_restaurants": {
            "destination": "Hoi An",
            "cuisine": "banh mi",
            "max_price_level": "low",
        },
        "search_attractions": {"destination": "Da Nang", "min_rating": 4.5},
        "search_hotels": {
            "destination": "Da Nang",
            "check_in": "2026-10-12",
            "check_out": "2026-10-15",
        },
        "search_flights": {
            "origin": "HAN",
            "destination": "DAD",
            "departure_date": "2026-10-12",
        },
        "get_weather": {"destination": "Hoi An", "forecast_date": "2026-10-12"},
        "calculate_route": {
            "origin_latitude": 16.0544,
            "origin_longitude": 108.2022,
            "destination_latitude": 15.8801,
            "destination_longitude": 108.3380,
            "travel_mode": "driving",
        },
        "get_trip_budget": {"trip_id": str(trip_service.trip_id)},
        "save_trip_activity": {
            "trip_day_id": str(trip_service.trip_day_id),
            "activity_type": "sightseeing",
            "estimated_cost": "250000",
        },
    }

    print("TripMind agent tool smoke test (no LLM)\n")
    for name, arguments in calls.items():
        print(f"=== {name} ===")
        print(json.dumps(tools[name].invoke(arguments), indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
