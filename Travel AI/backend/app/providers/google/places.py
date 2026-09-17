"""Google Places API (New) adapter implementing PlacesProvider."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.providers.base.places import PlacesProvider
from app.providers.errors import ProviderError
from app.providers.http import ProviderHttpClient
from app.providers.models import PlaceCategory, PlaceDetails, PlaceSearchRequest, PlaceSearchResult

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

_SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.types",
        "places.rating",
        "places.priceLevel",
        "places.shortFormattedAddress",
    ]
)
_DETAILS_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "types",
        "rating",
        "priceLevel",
        "websiteUri",
        "regularOpeningHours",
        "editorialSummary",
    ]
)

_CATEGORY_INCLUDED_TYPE = {
    PlaceCategory.RESTAURANT: "restaurant",
    PlaceCategory.HOTEL: "lodging",
    PlaceCategory.ATTRACTION: "tourist_attraction",
    PlaceCategory.LANDMARK: "tourist_attraction",
}

_PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": "low",
    "PRICE_LEVEL_INEXPENSIVE": "low",
    "PRICE_LEVEL_MODERATE": "medium",
    "PRICE_LEVEL_EXPENSIVE": "high",
    "PRICE_LEVEL_VERY_EXPENSIVE": "high",
}


class GooglePlacesProvider(PlacesProvider):
    """Normalized PlacesProvider backed by Google Places API (New)."""

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
            raise ValueError("GOOGLE_MAPS_API_KEY is required for GooglePlacesProvider.")
        self._api_key = api_key
        self._http = http_client or ProviderHttpClient(
            provider="google_places",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )

    def search_places(self, request: PlaceSearchRequest) -> List[PlaceSearchResult]:
        query_parts = [part for part in [request.query.strip(), request.destination] if part]
        text_query = " in ".join(query_parts) if len(query_parts) == 2 else (query_parts[0] if query_parts else "points of interest")
        body: Dict[str, Any] = {
            "textQuery": text_query,
            "maxResultCount": request.limit,
            "languageCode": "en",
        }
        if request.category is not None:
            body["includedType"] = _CATEGORY_INCLUDED_TYPE[request.category]

        payload = self._http.post_json(
            _SEARCH_URL,
            headers=self._headers(_SEARCH_FIELD_MASK),
            json_body=body,
        )
        places = payload.get("places") or []
        results: List[PlaceSearchResult] = []
        for item in places:
            mapped = self._to_search_result(item, fallback_destination=request.destination or "")
            if mapped is not None:
                results.append(mapped)
        logger.info("google_places search returned %s results", len(results))
        return results

    def get_place_details(self, place_id: str) -> Optional[PlaceDetails]:
        resource_id = place_id if place_id.startswith("places/") else f"places/{place_id}"
        url = f"https://places.googleapis.com/v1/{resource_id}"
        try:
            payload = self._http.get_json(url, headers=self._headers(_DETAILS_FIELD_MASK))
        except ProviderError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._to_place_details(payload)

    def _headers(self, field_mask: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
        }

    def _to_search_result(
        self, item: Dict[str, Any], *, fallback_destination: str
    ) -> Optional[PlaceSearchResult]:
        try:
            place_id = str(item.get("id") or "")
            name = (item.get("displayName") or {}).get("text") or ""
            location = item.get("location") or {}
            if not place_id or not name:
                return None
            types = list(item.get("types") or [])
            address = item.get("formattedAddress") or item.get("shortFormattedAddress") or ""
            return PlaceSearchResult(
                id=place_id,
                name=name,
                category=self._map_category(types),
                destination=fallback_destination or _destination_from_address(address),
                description=name,
                latitude=float(location.get("latitude", 0.0)),
                longitude=float(location.get("longitude", 0.0)),
                address=address,
                rating=_optional_float(item.get("rating")),
                tags=types[:8],
            )
        except (TypeError, ValueError) as exc:
            logger.warning("google_places skipped malformed search item: %s", type(exc).__name__)
            return None

    def _to_place_details(self, item: Dict[str, Any]) -> PlaceDetails:
        types = list(item.get("types") or [])
        address = item.get("formattedAddress") or ""
        location = item.get("location") or {}
        opening = item.get("regularOpeningHours") or {}
        weekday = opening.get("weekdayDescriptions") or []
        editorial = (item.get("editorialSummary") or {}).get("text")
        name = (item.get("displayName") or {}).get("text") or "Unknown place"
        return PlaceDetails(
            id=str(item.get("id") or ""),
            name=name,
            category=self._map_category(types),
            destination=_destination_from_address(address),
            description=editorial or name,
            latitude=float(location.get("latitude", 0.0)),
            longitude=float(location.get("longitude", 0.0)),
            address=address,
            rating=_optional_float(item.get("rating")),
            tags=types[:8],
            opening_hours="; ".join(weekday) if weekday else None,
            price_level=_PRICE_LEVEL_MAP.get(str(item.get("priceLevel") or ""), None),
            website=item.get("websiteUri"),
        )

    @staticmethod
    def _map_category(types: List[str]) -> PlaceCategory:
        lowered = {item.casefold() for item in types}
        if "restaurant" in lowered or "food" in lowered or "cafe" in lowered:
            return PlaceCategory.RESTAURANT
        if "lodging" in lowered:
            return PlaceCategory.HOTEL
        if "tourist_attraction" in lowered or "museum" in lowered or "park" in lowered:
            return PlaceCategory.ATTRACTION
        if "point_of_interest" in lowered or "establishment" in lowered:
            return PlaceCategory.LANDMARK
        return PlaceCategory.ATTRACTION


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _destination_from_address(address: str) -> str:
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else "Unknown"
