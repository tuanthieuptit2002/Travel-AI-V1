"""Nominatim (OpenStreetMap) geocoding helper.

Public instance policy: at most one request per second and a descriptive
``User-Agent`` header (https://operations.osmfoundation.org/policies/nominatim/).
Lookups are cached in-process and requests are throttled so a single trip plan
stays well inside that budget.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.providers.http import ProviderHttpClient

logger = logging.getLogger(__name__)

DEFAULT_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
DEFAULT_USER_AGENT = "TripMindAI/0.1 (+https://github.com/tunthieudev/Travel-AI-Agent)"
_CACHE_LIMIT = 512


class NominatimGeocoder:
    """Forward/reverse geocoding with in-process caching and request throttling."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_NOMINATIM_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 1.0,
        http_client: Optional[ProviderHttpClient] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._base_url = (base_url or DEFAULT_NOMINATIM_URL).rstrip("/")
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._min_interval = max(0.0, min_interval_seconds)
        self._http = http_client or ProviderHttpClient(
            provider="nominatim",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        self._last_request_at: Optional[float] = None
        self._forward_cache: Dict[str, Tuple[float, float, str]] = {}
        self._reverse_cache: Dict[str, str] = {}

    def geocode(self, query: str) -> Optional[Tuple[float, float, str]]:
        """Resolve a place name to ``(latitude, longitude, label)``; None when unknown."""
        key = " ".join((query or "").split()).casefold()
        if not key:
            return None
        cached = self._forward_cache.get(key)
        if cached is not None:
            return cached

        payload = self._get(
            "/search",
            {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
            },
        )
        if not isinstance(payload, list) or not payload:
            logger.info("nominatim found no match for query=%s", query)
            return None
        hit = payload[0]
        if not isinstance(hit, dict):
            logger.warning("nominatim returned a malformed search hit")
            return None
        try:
            latitude = float(hit["lat"])
            longitude = float(hit["lon"])
        except (KeyError, TypeError, ValueError):
            logger.warning("nominatim returned a malformed search hit")
            return None

        label = str(hit.get("name") or "").strip() or _label_from_address(hit)
        resolved = (latitude, longitude, label or query)
        _remember(self._forward_cache, key, resolved)
        return resolved

    def reverse(self, latitude: float, longitude: float) -> Optional[str]:
        """Resolve coordinates to a display address; None when unavailable."""
        key = f"{round(latitude, 5)},{round(longitude, 5)}"
        cached = self._reverse_cache.get(key)
        if cached is not None:
            return cached

        payload = self._get(
            "/reverse",
            {"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 18},
        )
        if not isinstance(payload, dict):
            logger.info("nominatim reverse geocoding returned no address")
            return None
        display = str(payload.get("display_name") or "").strip()
        if not display:
            return None
        _remember(self._reverse_cache, key, display)
        return display

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        self._respect_rate_limit()
        try:
            return self._http.get_json(
                f"{self._base_url}{path}",
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                params=params,
            )
        finally:
            self._last_request_at = time.monotonic()

    def _respect_rate_limit(self) -> None:
        if self._min_interval <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)


def _label_from_address(hit: Dict[str, Any]) -> str:
    address = hit.get("address")
    if isinstance(address, dict):
        for field in ("city", "town", "village", "municipality", "county", "state"):
            value = str(address.get(field) or "").strip()
            if value:
                return value
    display = str(hit.get("display_name") or "").strip()
    return display.split(",")[0].strip() if display else ""


def _remember(cache: Dict[str, Any], key: str, value: Any) -> None:
    if len(cache) >= _CACHE_LIMIT:
        cache.pop(next(iter(cache)))
    cache[key] = value