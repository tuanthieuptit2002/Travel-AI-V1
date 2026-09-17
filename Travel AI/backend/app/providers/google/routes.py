"""Google Routes API adapter implementing RouteProvider."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from app.providers.base.routes import RouteProvider
from app.providers.errors import ProviderError
from app.providers.geo import parse_lat_lng
from app.providers.http import ProviderHttpClient
from app.providers.models import RouteRequest, RouteResult, TravelMode

logger = logging.getLogger(__name__)

_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
_FIELD_MASK = "routes.duration,routes.distanceMeters"

_MODE_MAP = {
    TravelMode.DRIVING: "DRIVE",
    TravelMode.WALKING: "WALK",
    TravelMode.BICYCLING: "BICYCLE",
    TravelMode.TRANSIT: "TRANSIT",
}


class GoogleRoutesProvider(RouteProvider):
    """Normalized RouteProvider backed by Google Routes API."""

    def __init__(
        self,
        api_key: str,
        *,
        http_client: Optional[ProviderHttpClient] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY is required for GoogleRoutesProvider.")
        self._api_key = api_key
        self._http = http_client or ProviderHttpClient(
            provider="google_routes",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

    def calculate_route(self, request: RouteRequest) -> RouteResult:
        body = {
            "origin": self._waypoint(request.origin),
            "destination": self._waypoint(request.destination),
            "travelMode": _MODE_MAP[request.travel_mode],
            "languageCode": "en",
            "units": "METRIC",
        }
        payload = self._http.post_json(
            _ROUTES_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": _FIELD_MASK,
            },
            json_body=body,
        )
        routes = payload.get("routes") or []
        if not routes:
            raise ProviderError(
                "No route found between the given locations.",
                provider="google_routes",
                code="not_found",
                status_code=404,
            )
        route = routes[0]
        distance_m = float(route.get("distanceMeters") or 0)
        duration_minutes = _duration_to_minutes(str(route.get("duration") or "0s"))
        logger.info(
            "google_routes computed route distance_km=%.2f duration_min=%s",
            distance_m / 1000.0,
            duration_minutes,
        )
        return RouteResult(
            origin=request.origin,
            destination=request.destination,
            travel_mode=request.travel_mode,
            distance_km=round(distance_m / 1000.0, 1),
            duration_minutes=duration_minutes,
        )

    @staticmethod
    def _waypoint(value: str) -> Dict[str, Any]:
        coords = parse_lat_lng(value)
        if coords is None:
            return {"address": value}
        latitude, longitude = coords
        return {"location": {"latLng": {"latitude": latitude, "longitude": longitude}}}


def _duration_to_minutes(duration: str) -> int:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)s", duration.strip())
    if not match:
        return 0
    seconds = float(match.group(1))
    return max(0, int(round(seconds / 60.0)))
