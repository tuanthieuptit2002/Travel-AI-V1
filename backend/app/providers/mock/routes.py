from math import asin, cos, radians, sin, sqrt
from typing import Dict, Tuple

from app.providers.base.routes import RouteProvider
from app.providers.geo import parse_lat_lng
from app.providers.mock.catalog import VIETNAM_DESTINATIONS, normalize_destination
from app.providers.models import RouteRequest, RouteResult, TravelMode


class MockRouteProvider(RouteProvider):
    """Distance estimates using city centers; not suitable for navigation."""

    _MODE_SPEED_KPH: Dict[TravelMode, float] = {
        TravelMode.DRIVING: 55.0,
        TravelMode.TRANSIT: 42.0,
        TravelMode.BICYCLING: 15.0,
        TravelMode.WALKING: 5.0,
    }

    def calculate_route(self, request: RouteRequest) -> RouteResult:
        origin_name, origin_lat, origin_lon = self._resolve_point(request.origin)
        destination_name, destination_lat, destination_lon = self._resolve_point(request.destination)

        if origin_name == destination_name:
            return RouteResult(
                origin=origin_name,
                destination=destination_name,
                travel_mode=request.travel_mode,
                distance_km=0,
                duration_minutes=0,
            )

        direct_distance = self._haversine_km(origin_lat, origin_lon, destination_lat, destination_lon)
        multiplier = 1.18 if request.travel_mode == TravelMode.DRIVING else 1.0
        distance = round(direct_distance * multiplier, 1)
        duration = round((distance / self._MODE_SPEED_KPH[request.travel_mode]) * 60)
        return RouteResult(
            origin=origin_name,
            destination=destination_name,
            travel_mode=request.travel_mode,
            distance_km=distance,
            duration_minutes=duration,
        )

    def _resolve_point(self, value: str) -> Tuple[str, float, float]:
        coords = parse_lat_lng(value)
        if coords is not None:
            return self._nearest_city(*coords)

        key = normalize_destination(value)
        if key not in VIETNAM_DESTINATIONS:
            raise ValueError("Mock routes are available only between supported Vietnam destinations.")
        name, latitude, longitude = VIETNAM_DESTINATIONS[key]
        return name, latitude, longitude

    def _nearest_city(self, latitude: float, longitude: float) -> Tuple[str, float, float]:
        nearest = None
        nearest_distance = float("inf")
        for name, city_lat, city_lon in VIETNAM_DESTINATIONS.values():
            distance = self._haversine_km(latitude, longitude, city_lat, city_lon)
            if distance < nearest_distance:
                nearest = (name, city_lat, city_lon)
                nearest_distance = distance
        if nearest is None or nearest_distance > 80:
            raise ValueError("Coordinates are outside the supported mock geography.")
        return nearest

    @staticmethod
    def _haversine_km(lat_one: float, lon_one: float, lat_two: float, lon_two: float) -> float:
        latitude_delta = radians(lat_two - lat_one)
        longitude_delta = radians(lon_two - lon_one)
        value = (
            sin(latitude_delta / 2) ** 2
            + cos(radians(lat_one)) * cos(radians(lat_two)) * sin(longitude_delta / 2) ** 2
        )
        return 6371.0 * 2 * asin(sqrt(value))
