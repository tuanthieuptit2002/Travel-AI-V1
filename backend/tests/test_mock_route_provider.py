import pytest

from app.providers.mock import MockRouteProvider
from app.providers.models import RouteRequest, RouteResult, TravelMode


def test_route_provider_returns_typed_distance_and_duration() -> None:
    result = MockRouteProvider().calculate_route(
        RouteRequest(origin="Hanoi", destination="Ha Long", travel_mode=TravelMode.DRIVING)
    )

    assert isinstance(result, RouteResult)
    assert result.distance_km > 150
    assert result.duration_minutes > 0
    assert result.travel_mode is TravelMode.DRIVING


def test_route_provider_handles_same_destination_and_rejects_unknown_city() -> None:
    provider = MockRouteProvider()
    same_city = provider.calculate_route(RouteRequest(origin="Da Nang", destination="Danang"))

    assert same_city.distance_km == 0
    assert same_city.duration_minutes == 0
    with pytest.raises(ValueError, match="supported Vietnam destinations"):
        provider.calculate_route(RouteRequest(origin="Hanoi", destination="Bangkok"))
