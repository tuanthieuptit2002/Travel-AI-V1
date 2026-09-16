"""OSRM routing adapter implementing RouteProvider (keyless OpenStreetMap data).

The public demo server exposes driving/foot/bike profiles only; transit raises a
structured ProviderError so the agent can degrade instead of inventing a route.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.providers.base.routes import RouteProvider
from app.providers.errors import ProviderError
from app.providers.geo import parse_lat_lng
from app.providers.http import ProviderHttpClient
from app.providers.models import RouteRequest, RouteResult, TravelMode
from app.providers.osm.geocoding import DEFAULT_USER_AGENT, NominatimGeocoder

logger = logging.getLogger(__name__)

DEFAULT_OSRM_URL = "https://router.project-osrm.org"

_PROFILE_BY_MODE: Dict[TravelMode, str] = {
    TravelMode.DRIVING: "driving",
    TravelMode.WALKING: "foot",
    TravelMode.BICYCLING: "bike",
}


class OsmRoutesProvider(RouteProvider):
    """Normalized RouteProvider backed by an OSRM instance."""

    def __init__(
        self,
        *,
        osrm_url: str = DEFAULT_OSRM_URL,
        geocoder: Optional[NominatimGeocoder] = None,
        nominatim_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 1.0,
        http_client: Optional[ProviderHttpClient] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._osrm_url = (osrm_url or DEFAULT_OSRM_URL).rstrip("/")
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._http = http_client or ProviderHttpClient(
            provider="osrm",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        self._geocoder = geocoder or NominatimGeocoder(
            base_url=nominatim_url,
            user_agent=user_agent,
            min_interval_seconds=min_interval_seconds,
            http_client=http_client,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

    def calculate_route(self, request: RouteRequest) -> RouteResult:
        profile = _PROFILE_BY_MODE.get(request.travel_mode)
        if profile is None:
            raise ProviderError(
                "OpenStreetMap routing does not support this travel mode.",
                provider="osrm",
                code="unsupported_travel_mode",
                status_code=400,
            )

        origin_lat, origin_lon = self._resolve_point(request.origin)
        destination_lat, destination_lon = self._resolve_point(request.destination)
        if (origin_lat, origin_lon) == (destination_lat, destination_lon):
            return RouteResult(
                origin=request.origin,
                destination=request.destination,
                travel_mode=request.travel_mode,
                distance_km=0,
                duration_minutes=0,
            )

        coordinates = (
            f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
        )
        payload = self._route_request(coordinates, profile)
        if not isinstance(payload, dict):
            raise ProviderError(
                "Upstream provider returned an unexpected routing payload.",
                provider="osrm",
                code="upstream_error",
                status_code=502,
            )

        code = str(payload.get("code") or "")
        routes = payload.get("routes") or []
        if code == "NoRoute" or not routes:
            raise ProviderError(
                "No route found between the given locations.",
                provider="osrm",
                code="not_found",
                status_code=404,
            )
        if code and code != "Ok":
            raise ProviderError(
                "OSRM rejected the routing request.",
                provider="osrm",
                code="upstream_error",
                status_code=400,
            )

        route = routes[0]
        distance_km = round(_as_float(route.get("distance")) / 1000.0, 1)
        duration_minutes = max(0, int(round(_as_float(route.get("duration")) / 60.0)))
        logger.info(
            "osrm computed route distance_km=%.2f duration_min=%s profile=%s",
            distance_km,
            duration_minutes,
            profile,
        )
        return RouteResult(
            origin=request.origin,
            destination=request.destination,
            travel_mode=request.travel_mode,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
        )

    def _resolve_point(self, value: str) -> Tuple[float, float]:
        coords = parse_lat_lng(value or "")
        if coords is not None:
            return coords
        resolved = self._geocoder.geocode(value)
        if resolved is None:
            raise ProviderError(
                "Route waypoint could not be geocoded.",
                provider="nominatim",
                code="geocode_not_found",
                status_code=404,
            )
        return resolved[0], resolved[1]

    def _route_request(self, coordinates: str, profile: str) -> Any:
        """GET a route, downgrading https -> http once when TLS cannot be negotiated.

        Some hosts (and old client TLS stacks, e.g. macOS LibreSSL) fail the https
        handshake to public OSRM instances. OSRM serves the same public, non-sensitive
        payload over plain HTTP, so a single self-healing downgrade keeps routing
        available instead of failing every call.
        """
        params = {"overview": "false", "alternatives": "false", "steps": "false"}
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        base = self._osrm_url
        try:
            return self._http.get_json(
                f"{base}/route/v1/{profile}/{coordinates}",
                headers=headers,
                params=params,
            )
        except ProviderError as exc:
            if exc.code not in {"transport_error", "timeout", "retry_exhausted"}:
                raise
            if not base.startswith("https://"):
                raise
            fallback = "http://" + base[len("https://"):]
            logger.warning("osrm https request failed (%s); retrying over http", exc.code)
            self._osrm_url = fallback
            return self._http.get_json(
                f"{fallback}/route/v1/{profile}/{coordinates}",
                headers=headers,
                params=params,
            )


def _as_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0