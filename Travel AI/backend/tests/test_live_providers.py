from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.core.config import Settings
from app.providers.errors import ProviderError
from app.providers.factory import build_tool_dependencies
from app.providers.http import ProviderHttpClient
from app.providers.mock import MockPlacesProvider, MockRouteProvider, MockWeatherProvider
from app.providers.models import (
    RouteRequest,
    TravelMode,
    WeatherRequest,
)
from app.providers.open_meteo import OpenMeteoProvider
from app.tools import ToolDependencies


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, timeout=5.0)


def test_http_client_retries_rate_limit_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow down"})
        return httpx.Response(200, json={"ok": True})

    client = ProviderHttpClient(
        provider="test",
        timeout_seconds=1,
        max_retries=3,
        backoff_seconds=0,
        client=_mock_client(handler),
    )
    payload = client.get_json("https://example.test/resource")
    assert payload == {"ok": True}
    assert attempts["count"] == 3


def test_http_client_raises_structured_error_without_leaking_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom", "api_key": "should-not-surface"})

    client = ProviderHttpClient(
        provider="test",
        timeout_seconds=1,
        max_retries=0,
        client=_mock_client(handler),
    )
    with pytest.raises(ProviderError) as exc:
        client.get_json("https://example.test/resource?key=SECRET")
    assert exc.value.code == "upstream_error"
    assert "SECRET" not in str(exc.value)


def test_open_meteo_provider_geocodes_and_forecasts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding-api" in str(request.url):
            return httpx.Response(
                200,
                json={"results": [{"name": "Da Nang", "latitude": 16.05, "longitude": 108.2}]},
            )
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2026-10-12"],
                    "weathercode": [80],
                    "temperature_2m_max": [31.0],
                    "temperature_2m_min": [23.0],
                    "precipitation_probability_max": [55],
                    "windspeed_10m_max": [14.0],
                    "relative_humidity_2m_mean": [78],
                }
            },
        )

    http = ProviderHttpClient(
        provider="open_meteo",
        max_retries=0,
        client=_mock_client(handler),
    )
    provider = OpenMeteoProvider(
        base_url="https://api.open-meteo.com",
        geocoding_url="https://geocoding-api.open-meteo.com",
        http_client=http,
    )
    weather = provider.get_weather(
        WeatherRequest(destination="Da Nang", forecast_date=date(2026, 10, 12))
    )
    assert weather.condition == "slight rain showers"
    assert weather.temperature_max_c == 31.0
    assert weather.precipitation_probability == 55


def test_build_tool_dependencies_defaults_to_mocks() -> None:
    deps = build_tool_dependencies(Settings(travel_data_mode="mock"))
    assert isinstance(deps.places, MockPlacesProvider)
    assert isinstance(deps.routes, MockRouteProvider)
    assert isinstance(deps.weather, MockWeatherProvider)


def test_build_tool_dependencies_live_uses_curated_place_suggestions() -> None:
    deps = build_tool_dependencies(
        Settings(
            travel_data_mode="live",
            open_meteo_base_url="https://api.open-meteo.com",
        )
    )
    assert isinstance(deps.places, MockPlacesProvider)
    assert isinstance(deps.routes, MockRouteProvider)
    assert isinstance(deps.weather, OpenMeteoProvider)


def test_tool_dependencies_from_settings_matches_factory() -> None:
    deps = ToolDependencies.from_settings()
    assert deps.places is not None
    assert deps.weather is not None
    assert deps.routes is not None


def test_mock_route_provider_accepts_coordinate_pairs() -> None:
    result = MockRouteProvider().calculate_route(
        RouteRequest(
            origin="16.0544,108.2022",
            destination="15.8801,108.3380",
            travel_mode=TravelMode.DRIVING,
        )
    )
    assert result.origin == "Da Nang"
    assert result.destination == "Hoi An"
    assert result.distance_km > 0
