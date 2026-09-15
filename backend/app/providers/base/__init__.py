"""Abstract provider contracts. Application code depends only on these contracts."""

from app.providers.base.flights import FlightProvider
from app.providers.base.hotels import HotelProvider
from app.providers.base.places import PlacesProvider
from app.providers.base.routes import RouteProvider
from app.providers.base.weather import WeatherProvider

__all__ = ["FlightProvider", "HotelProvider", "PlacesProvider", "RouteProvider", "WeatherProvider"]
