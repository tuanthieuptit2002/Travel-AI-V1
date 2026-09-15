import pytest

from app.providers.base import FlightProvider, HotelProvider, PlacesProvider, RouteProvider, WeatherProvider


@pytest.mark.parametrize("provider", [PlacesProvider, WeatherProvider, RouteProvider, FlightProvider, HotelProvider])
def test_provider_contracts_cannot_be_instantiated(provider: object) -> None:
    with pytest.raises(TypeError):
        provider()  # type: ignore[operator]
