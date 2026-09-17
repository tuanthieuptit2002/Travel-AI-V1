from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.tools import StructuredTool

from app.providers.base import FlightProvider, HotelProvider
from app.providers.mock import MockPlacesProvider, MockRouteProvider, MockWeatherProvider
from app.providers.models import (
    FlightSearchRequest,
    FlightSearchResult,
    HotelSearchRequest,
    HotelSearchResult,
)
from app.services.trip_service import TripBudgetSummary
from app.tools import (
    ALL_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    ToolDependencies,
    create_agent_tools,
    create_read_only_tools,
    create_write_tools,
)


class FakeTripService:
    def __init__(self) -> None:
        self.trip_id = uuid4()
        self.trip_day_id = uuid4()
        self.activity_id = uuid4()
        self.last_command = None

    def get_budget(self, trip_id: object) -> TripBudgetSummary | None:
        if trip_id != self.trip_id:
            return None
        return TripBudgetSummary(
            trip_id=self.trip_id,
            total_budget=Decimal("8000000"),
            scheduled_cost=Decimal("1200000"),
            remaining_budget=Decimal("6800000"),
            currency="VND",
        )

    def save_trip_activity(self, command: object) -> SimpleNamespace:
        self.last_command = command
        return SimpleNamespace(
            id=self.activity_id,
            trip_day_id=self.trip_day_id,
            place_id=None,
            activity_type="sightseeing",
            order_index=1,
            estimated_cost=Decimal("250000"),
        )


class FakeFlightProvider(FlightProvider):
    def search_flights(self, request: FlightSearchRequest) -> list[FlightSearchResult]:
        return [
            FlightSearchResult(
                id="fake-flight-1",
                airline="Vietnam Airlines",
                flight_number="VN123",
                departure_at=datetime(2026, 10, 12, 8, 0),
                arrival_at=datetime(2026, 10, 12, 9, 30),
                origin=request.origin,
                destination=request.destination,
                price=1850000,
                currency=request.currency,
                stops=0,
            )
        ]


class FakeHotelProvider(HotelProvider):
    def search_hotels(self, request: HotelSearchRequest) -> list[HotelSearchResult]:
        return [
            HotelSearchResult(
                id="fake-hotel-1",
                name="Mock Riverside Hotel",
                destination=request.destination,
                address="1 River Road",
                latitude=16.05,
                longitude=108.2,
                rating=4.5,
                nightly_price=1200000,
                currency=request.currency,
                amenities=["wifi", "breakfast"],
            )
        ]


class LeakyWeatherProvider:
    """Simulates a provider that raises credential-bearing errors."""

    def get_weather(self, request: object) -> object:
        raise RuntimeError("Open-Meteo failed using api_key=sk-secret-should-never-leak")


def _tools(**overrides: object) -> dict[str, StructuredTool]:
    config = {
        "places": MockPlacesProvider(),
        "weather": MockWeatherProvider(),
        "routes": MockRouteProvider(),
    }
    config.update(overrides)
    dependencies = ToolDependencies(**config)  # type: ignore[arg-type]
    return {tool.name: tool for tool in create_agent_tools(dependencies)}


def test_tool_registry_separates_read_and_write_operations() -> None:
    assert READ_ONLY_TOOL_NAMES.isdisjoint(WRITE_TOOL_NAMES)
    assert ALL_TOOL_NAMES == READ_ONLY_TOOL_NAMES | WRITE_TOOL_NAMES
    assert WRITE_TOOL_NAMES == {"save_trip_activity", "update_user_memory"}

    read_names = {tool.name for tool in create_read_only_tools()}
    write_names = {tool.name for tool in create_write_tools()}
    assert read_names == READ_ONLY_TOOL_NAMES
    assert write_names == WRITE_TOOL_NAMES


def test_every_tool_has_a_name_description_and_typed_schema() -> None:
    tools = create_agent_tools()
    assert {tool.name for tool in tools} == ALL_TOOL_NAMES
    for tool in tools:
        assert isinstance(tool, StructuredTool)
        assert tool.description
        assert tool.args_schema is not None


def test_search_places() -> None:
    result = _tools()["search_places"].invoke({"destination": "Da Nang", "query": "beach"})
    assert result["success"] is True
    assert result["places"][0]["name"] == "My Khe Beach"
    assert "raw" not in result
    assert "api_key" not in str(result).casefold()


def test_search_places_filters_by_radius() -> None:
    result = _tools()["search_places"].invoke(
        {
            "destination": "Da Nang",
            "query": "",
            "latitude": 16.0544,
            "longitude": 108.2467,
            "radius_km": 2,
        }
    )
    assert result["success"] is True
    assert any(place["id"] == "vn-danang-my-khe" for place in result["places"])
    assert all(
        place["id"] != "vn-danang-marble-mountains" for place in result["places"]
    )


def test_get_place_details() -> None:
    result = _tools()["get_place_details"].invoke({"place_id": "vn-danang-my-khe"})
    assert result["success"] is True
    assert result["place"]["opening_hours"]
    assert result["place"]["id"] == "vn-danang-my-khe"


def test_get_place_details_not_found() -> None:
    result = _tools()["get_place_details"].invoke({"place_id": "missing-place"})
    assert result == {"success": False, "error": "Place was not found.", "place": None}


def test_search_restaurants() -> None:
    result = _tools()["search_restaurants"].invoke(
        {"destination": "Hoi An", "max_price_level": "low"}
    )
    assert result["success"] is True
    assert result["restaurants"][0]["name"] == "Banh Mi Phuong"
    assert result["restaurants"][0]["category"] == "restaurant"


def test_search_attractions() -> None:
    result = _tools()["search_attractions"].invoke(
        {"destination": "Da Nang", "min_rating": 4.5}
    )
    assert result["success"] is True
    assert result["attractions"]
    assert all(item["category"] == "attraction" for item in result["attractions"])


def test_search_hotels_unconfigured() -> None:
    result = _tools()["search_hotels"].invoke(
        {
            "destination": "Da Nang",
            "check_in": "2026-10-12",
            "check_out": "2026-10-15",
        }
    )
    assert result == {
        "success": False,
        "error": "Hotel search is not configured.",
        "hotels": [],
    }


def test_search_hotels_with_provider() -> None:
    result = _tools(hotels=FakeHotelProvider())["search_hotels"].invoke(
        {
            "destination": "Da Nang",
            "check_in": "2026-10-12",
            "check_out": "2026-10-15",
        }
    )
    assert result["success"] is True
    assert result["hotels"][0]["name"] == "Mock Riverside Hotel"
    assert result["hotels"][0]["currency"] == "VND"


def test_search_flights_unconfigured() -> None:
    result = _tools()["search_flights"].invoke(
        {"origin": "HAN", "destination": "DAD", "departure_date": "2026-10-12"}
    )
    assert result == {
        "success": False,
        "error": "Flight search is not configured.",
        "flights": [],
    }


def test_search_flights_with_provider() -> None:
    result = _tools(flights=FakeFlightProvider())["search_flights"].invoke(
        {"origin": "han", "destination": "dad", "departure_date": "2026-10-12"}
    )
    assert result["success"] is True
    assert result["flights"][0]["flight_number"] == "VN123"
    assert result["flights"][0]["origin"] == "HAN"


def test_get_weather() -> None:
    result = _tools()["get_weather"].invoke(
        {"destination": "Hoi An", "forecast_date": "2026-10-12"}
    )
    assert result["success"] is True
    assert result["weather"]["condition"] == "scattered showers"


def test_calculate_route() -> None:
    result = _tools()["calculate_route"].invoke(
        {
            "origin_latitude": 16.0544,
            "origin_longitude": 108.2022,
            "destination_latitude": 15.8801,
            "destination_longitude": 108.3380,
            "travel_mode": "driving",
        }
    )
    assert result["success"] is True
    assert result["route"]["distance_km"] > 0
    assert result["route"]["origin"] == "Da Nang"
    assert result["route"]["destination"] == "Hoi An"


def test_get_trip_budget_unconfigured() -> None:
    result = _tools()["get_trip_budget"].invoke({"trip_id": str(uuid4())})
    assert result["success"] is False
    assert "configured" in result["error"]


def test_get_trip_budget_via_service() -> None:
    fake_service = FakeTripService()
    result = _tools(trip_service=fake_service)["get_trip_budget"].invoke(
        {"trip_id": str(fake_service.trip_id)}
    )
    assert result["success"] is True
    assert result["remaining_budget"] == "6800000"
    assert result["currency"] == "VND"


def test_save_trip_activity_unconfigured() -> None:
    result = _tools()["save_trip_activity"].invoke(
        {"trip_day_id": str(uuid4()), "activity_type": "sightseeing"}
    )
    assert result["success"] is False
    assert "configured" in result["error"]


def test_save_trip_activity_via_service() -> None:
    fake_service = FakeTripService()
    result = _tools(trip_service=fake_service)["save_trip_activity"].invoke(
        {
            "trip_day_id": str(fake_service.trip_day_id),
            "activity_type": "sightseeing",
            "estimated_cost": "250000",
        }
    )
    assert result["success"] is True
    assert result["activity"]["id"] == str(fake_service.activity_id)
    assert fake_service.last_command is not None


def test_provider_errors_are_safely_sanitized() -> None:
    from app.cache import clear_local_caches

    clear_local_caches()
    tools = _tools(weather=LeakyWeatherProvider())
    result = tools["get_weather"].invoke(
        {"destination": "Hoi An", "forecast_date": "2026-10-12"}
    )
    assert result == {
        "success": False,
        "error": "Unable to retrieve weather right now.",
        "weather": None,
    }
    assert "sk-secret" not in str(result)
    assert "api_key" not in str(result).casefold()


def test_unknown_destination_weather_is_sanitized() -> None:
    result = _tools()["get_weather"].invoke(
        {"destination": "Tokyo", "forecast_date": "2026-10-12"}
    )
    assert result == {
        "success": False,
        "error": "Unable to retrieve weather right now.",
        "weather": None,
    }


def test_agent_tool_surface_excludes_dangerous_capabilities() -> None:
    names = {tool.name for tool in create_agent_tools()}
    forbidden = {
        "python",
        "python_repl",
        "shell",
        "terminal",
        "bash",
        "sql",
        "database",
        "execute",
        "eval",
        "run_code",
    }
    assert names.isdisjoint(forbidden)
    for tool in create_agent_tools():
        assert "shell" not in tool.description.casefold()
        assert "python" not in tool.description.casefold()
        assert "sql" not in tool.description.casefold()


@pytest.mark.parametrize(
    "tool_name",
    sorted(ALL_TOOL_NAMES),
)
def test_each_registered_tool_is_invokable(tool_name: str) -> None:
    """Smoke-level invoke for every tool name with minimal valid arguments."""
    fake_service = FakeTripService()
    tools = _tools(
        flights=FakeFlightProvider(),
        hotels=FakeHotelProvider(),
        trip_service=fake_service,
    )
    payloads = {
        "search_places": {"destination": "Da Nang", "query": "beach"},
        "get_place_details": {"place_id": "vn-danang-my-khe"},
        "search_restaurants": {"destination": "Hoi An"},
        "search_attractions": {"destination": "Da Nang"},
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
        "get_trip_budget": {"trip_id": str(fake_service.trip_id)},
        "save_trip_activity": {
            "trip_day_id": str(fake_service.trip_day_id),
            "activity_type": "sightseeing",
        },
        "search_travel_knowledge": {
            "query": "local customs and food tips",
            "destination": "Da Nang",
            "top_k": 3,
        },
        "retrieve_user_memory": {"user_id": str(uuid4())},
        "update_user_memory": {
            "user_id": str(uuid4()),
            "field": "preferred_activities",
            "value": ["beaches"],
            "evidence": "explicit_user_statement",
            "source_excerpt": "I like beaches",
        },
    }
    result = tools[tool_name].invoke(payloads[tool_name])
    assert isinstance(result, dict)
    assert "success" in result
