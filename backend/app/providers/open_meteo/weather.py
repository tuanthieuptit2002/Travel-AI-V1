"""Open-Meteo weather adapter implementing WeatherProvider."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.providers.base.weather import WeatherProvider
from app.providers.errors import ProviderError
from app.providers.http import ProviderHttpClient
from app.providers.models import WeatherRequest, WeatherResult

logger = logging.getLogger(__name__)

# WMO weather interpretation codes (condensed).
_WMO_CONDITIONS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class OpenMeteoProvider(WeatherProvider):
    """Normalized WeatherProvider backed by Open-Meteo forecast + geocoding."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.open-meteo.com",
        geocoding_url: str = "https://geocoding-api.open-meteo.com",
        http_client: Optional[ProviderHttpClient] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._geocoding_url = geocoding_url.rstrip("/")
        self._http = http_client or ProviderHttpClient(
            provider="open_meteo",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        self._geo_cache: Dict[str, Tuple[float, float, str]] = {}

    def get_weather(self, request: WeatherRequest) -> WeatherResult:
        latitude, longitude, resolved_name = self._geocode(request.destination)
        day = request.forecast_date.isoformat()
        payload = self._http.get_json(
            f"{self._base_url}/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": ",".join(
                    [
                        "weathercode",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max",
                        "windspeed_10m_max",
                        "relative_humidity_2m_mean",
                    ]
                ),
                "timezone": "auto",
                "start_date": day,
                "end_date": day,
            },
        )
        daily = payload.get("daily") or {}
        times = daily.get("time") or []
        if not times:
            raise ProviderError(
                "No forecast data returned for the requested date.",
                provider="open_meteo",
                code="not_found",
                status_code=404,
            )

        index = 0
        weather_code = _first_int(daily.get("weathercode"), index)
        humidity = _first_int(daily.get("relative_humidity_2m_mean"), index)
        precip = _first_int(daily.get("precipitation_probability_max"), index)
        result = WeatherResult(
            destination=resolved_name or request.destination,
            forecast_date=request.forecast_date,
            condition=_WMO_CONDITIONS.get(weather_code, "unknown"),
            temperature_min_c=float(_first_number(daily.get("temperature_2m_min"), index)),
            temperature_max_c=float(_first_number(daily.get("temperature_2m_max"), index)),
            precipitation_probability=max(0, min(100, precip)),
            humidity_percent=max(0, min(100, humidity if humidity else 70)),
            wind_speed_kph=float(_first_number(daily.get("windspeed_10m_max"), index)),
        )
        logger.info(
            "open_meteo forecast destination=%s date=%s condition=%s",
            result.destination,
            result.forecast_date.isoformat(),
            result.condition,
        )
        return result

    def _geocode(self, destination: str) -> Tuple[float, float, str]:
        key = destination.casefold().strip()
        if key in self._geo_cache:
            return self._geo_cache[key]

        payload = self._http.get_json(
            f"{self._geocoding_url}/v1/search",
            params={"name": destination, "count": 1, "language": "en", "format": "json"},
        )
        results = payload.get("results") or []
        if not results:
            raise ProviderError(
                "Destination could not be geocoded.",
                provider="open_meteo",
                code="geocode_not_found",
                status_code=404,
            )
        hit = results[0]
        coords = (
            float(hit["latitude"]),
            float(hit["longitude"]),
            str(hit.get("name") or destination),
        )
        self._geo_cache[key] = coords
        return coords


def _first_number(values: Any, index: int) -> float:
    if not isinstance(values, list) or len(values) <= index or values[index] is None:
        return 0.0
    return float(values[index])


def _first_int(values: Any, index: int) -> int:
    return int(round(_first_number(values, index)))
