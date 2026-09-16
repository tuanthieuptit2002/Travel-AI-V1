"""OpenStreetMap places adapter: Overpass API for POIs, Nominatim for geocoding.

No API key is required. Overpass is shared community infrastructure, so a search
issues a single ``around`` query, fetches a bounded number of elements, and
caches normalized results so ``get_place_details`` never re-queries upstream for
identifiers that came from a search.

Place identifiers are opaque TripMind ids of the form ``osm:<type>/<id>``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.providers.base.places import PlacesProvider
from app.providers.errors import ProviderError
from app.providers.geo import parse_lat_lng
from app.providers.http import ProviderHttpClient
from app.providers.models import (
    PlaceCategory,
    PlaceDetails,
    PlaceSearchRequest,
    PlaceSearchResult,
)
from app.providers.osm.geocoding import DEFAULT_USER_AGENT, NominatimGeocoder

logger = logging.getLogger(__name__)

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api"

_OVERPASS_QUERY_TIMEOUT_SECONDS = 20
_OVERPASS_DEFAULT_TIMEOUT_SECONDS = 25.0
_MAX_FETCHED_ELEMENTS = 60
_DETAIL_CACHE_LIMIT = 512
_MAX_NAME_TERMS = 3
_MAX_TERM_LENGTH = 24
_ELEMENT_TYPES = frozenset({"node", "way", "relation"})

# Overpass tag selectors per TripMind place category: (tag key, value regex).
_CATEGORY_SELECTORS: Dict[PlaceCategory, Tuple[Tuple[str, str], ...]] = {
    PlaceCategory.RESTAURANT: (
        ("amenity", "^(restaurant|cafe|fast_food|food_court|ice_cream)$"),
        ("shop", "^(bakery|confectionery|deli)$"),
    ),
    PlaceCategory.HOTEL: (
        ("tourism", "^(hotel|hostel|guest_house|motel|apartment|chalet)$"),
    ),
    PlaceCategory.ATTRACTION: (
        ("tourism", "^(attraction|museum|viewpoint|artwork|gallery|zoo|theme_park|aquarium)$"),
        ("leisure", "^(park|garden|nature_reserve|beach_resort|water_park)$"),
        ("historic", ""),
    ),
    PlaceCategory.LANDMARK: (
        ("historic", ""),
        ("man_made", "^(tower|lighthouse|bridge|pier)$"),
        ("tourism", "^(attraction|viewpoint)$"),
        ("place", "^(city|town)$"),
    ),
}

_DEFAULT_SELECTORS: Tuple[Tuple[str, str], ...] = (
    ("tourism", "^(attraction|museum|viewpoint|gallery)$"),
    ("historic", ""),
    ("leisure", "^(park|garden|beach_resort)$"),
    ("amenity", "^(restaurant|cafe)$"),
    ("shop", "^(bakery|confectionery)$"),
)

_LODGING_VALUES = frozenset({"hotel", "hostel", "guest_house", "motel", "apartment", "chalet"})
_FOOD_AMENITY_VALUES = frozenset(
    {"restaurant", "cafe", "fast_food", "food_court", "ice_cream", "bar", "pub"}
)
_FOOD_SHOP_VALUES = frozenset({"bakery", "confectionery", "deli"})
_ATTRACTION_TOURISM_VALUES = frozenset(
    {"attraction", "museum", "viewpoint", "artwork", "gallery", "zoo", "theme_park", "aquarium"}
)
_ATTRACTION_LEISURE_VALUES = frozenset(
    {"park", "garden", "nature_reserve", "beach_resort", "water_park"}
)
# Keys whose OSM values are emitted as planning keywords; the agent layer matches
# plain lowercase tokens (e.g. "beach", "cafe", "museum") against place tags.
_INFO_VALUE_KEYS = (
    "tourism",
    "amenity",
    "historic",
    "leisure",
    "shop",
    "man_made",
    "natural",
    "beach",
    "place",
)
_KIND_TAG_KEYS = ("tourism", "amenity", "historic", "leisure", "shop", "man_made", "place")

# A plain outdoor-name query such as "beach" would otherwise miss OSM elements
# tagged as coastline / bay / island / beach_resort, so those imply a beachy match.
_BEACHY = frozenset(
    {
        "beach",
        "beaches",
        "beach resort",
        "bien",
        "coast",
        "coastline",
        "bay",
        "island",
        "cape",
        "peninsula",
        "reef",
        "shoal",
    }
)


class OsmPlacesProvider(PlacesProvider):
    """Normalized PlacesProvider backed by Overpass (search) and Nominatim (geocoding)."""

    def __init__(
        self,
        *,
        overpass_url: str = DEFAULT_OVERPASS_URL,
        nominatim_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 1.0,
        search_radius_km: float = 12.0,
        geocoder: Optional[NominatimGeocoder] = None,
        http_client: Optional[ProviderHttpClient] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._overpass_url = (overpass_url or DEFAULT_OVERPASS_URL).rstrip("/")
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._radius_m = int(max(1.0, search_radius_km) * 1000)
        self._http = http_client or ProviderHttpClient(
            provider="overpass",
            timeout_seconds=max(timeout_seconds, _OVERPASS_DEFAULT_TIMEOUT_SECONDS),
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
        self._details_cache: Dict[str, PlaceDetails] = {}

    def search_places(self, request: PlaceSearchRequest) -> List[PlaceSearchResult]:
        """Search POIs around a destination.

        The destination is geocoded with Nominatim (a coordinate string such as
        ``16.05,108.22`` skips that step); when no destination is given the query
        itself is used as the geocoding hint.
        """
        latitude, longitude, label = self._resolve_destination(request.destination, request.query)
        selectors = _CATEGORY_SELECTORS.get(request.category, _DEFAULT_SELECTORS)
        variants, terms = _search_terms(request.query)
        fetch_limit = min(_MAX_FETCHED_ELEMENTS, max(request.limit * 4, 10))

        elements = self._overpass(
            _build_query(latitude, longitude, self._radius_m, selectors, variants, fetch_limit)
        )
        results = self._normalize(elements, label, request.category, terms, require_all_terms=True)

        if not results and terms:
            # A named search can be too narrow for OSM tagging; retry by category only.
            logger.info("overpass name filter matched nothing; retrying category search")
            elements = self._overpass(
                _build_query(latitude, longitude, self._radius_m, selectors, (), fetch_limit)
            )
            results = self._normalize(
                elements, label, request.category, terms, require_all_terms=False
            )

        logger.info("osm_places search returned %s results", len(results))
        return results[: request.limit]

    def get_place_details(self, place_id: str) -> Optional[PlaceDetails]:
        cached = self._details_cache.get(place_id)
        if cached is not None:
            return cached

        parsed = _parse_place_id(place_id)
        if parsed is None:
            logger.info("osm_places received an unknown place id")
            return None
        element_type, element_id = parsed
        query = (
            f"[out:json][timeout:{_OVERPASS_QUERY_TIMEOUT_SECONDS}];\n"
            f"{element_type}({element_id});\n"
            "out center tags;"
        )
        elements = self._overpass(query)
        if not elements:
            return None
        details = self._to_details(elements[0], fallback_destination="")
        if details is not None:
            self._remember_details(details)
        return details

    def _resolve_destination(
        self, destination: Optional[str], query: str
    ) -> Tuple[float, float, str]:
        coords = parse_lat_lng(destination or "")
        if coords is not None:
            return coords[0], coords[1], (destination or "").strip()

        hint = (destination or "").strip() or (query or "").strip()
        if not hint:
            raise ProviderError(
                "A destination is required for OpenStreetMap place search.",
                provider="overpass",
                code="invalid_request",
                status_code=400,
            )
        resolved = self._geocoder.geocode(hint)
        if resolved is None:
            raise ProviderError(
                "Destination could not be geocoded.",
                provider="nominatim",
                code="geocode_not_found",
                status_code=404,
            )
        return resolved

    def _overpass(self, query: str) -> List[Dict[str, Any]]:
        payload = self._http.get_json(
            f"{self._overpass_url}/interpreter",
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            params={"data": query},
        )
        if not isinstance(payload, dict):
            logger.warning("overpass returned an unexpected payload")
            return []
        raw = payload.get("elements")
        elements = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        if not elements and payload.get("remark"):
            logger.warning("overpass returned no elements for the query")
        return elements

    def _normalize(
        self,
        elements: Sequence[Dict[str, Any]],
        destination: str,
        category: Optional[PlaceCategory],
        terms: Sequence[str],
        *,
        require_all_terms: bool,
    ) -> List[PlaceSearchResult]:
        matched: List[PlaceSearchResult] = []
        loose: List[PlaceSearchResult] = []
        seen: set[str] = set()
        for element in elements:
            details = self._to_details(element, fallback_destination=destination)
            if details is None or details.id in seen:
                continue
            if category is not None and details.category is not category:
                continue
            seen.add(details.id)
            self._remember_details(details)
            if not terms:
                matched.append(_as_search_result(details))
                continue
            searchable = _fold_accents(
                " ".join(
                    [details.name, details.description, details.address, destination]
                    + details.tags
                ).casefold()
            )
            if terms and "beach" in terms:
                tag_tokens = set(_fold_accents(tag).strip() for tag in details.tags)
                if tag_tokens & _BEACHY or any(
                    marker in searchable for marker in ("beach", "beaches", "bien", "biển")
                ):
                    matched.append(_as_search_result(details))
                    continue
            if all(term in searchable for term in terms):
                matched.append(_as_search_result(details))
            elif not require_all_terms and any(term in searchable for term in terms):
                loose.append(_as_search_result(details))
        if matched:
            return matched
        return loose if not require_all_terms else []

    def _to_details(
        self, element: Dict[str, Any], *, fallback_destination: str
    ) -> Optional[PlaceDetails]:
        tags = element.get("tags")
        if not isinstance(tags, dict) or not tags:
            return None
        name = str(tags.get("name") or tags.get("name:en") or "").strip()
        if not name:
            return None
        coords = _element_coords(element)
        place_id = _element_id(element)
        if coords is None or place_id is None:
            return None
        latitude, longitude = coords
        destination = _city_from_tags(tags) or fallback_destination or "OpenStreetMap"
        return PlaceDetails(
            id=place_id,
            name=name,
            category=_category_from_tags(tags),
            destination=destination,
            description=_describe(tags, destination),
            latitude=latitude,
            longitude=longitude,
            address=_address_from_tags(tags),
            rating=None,
            tags=_info_tags(tags),
            opening_hours=_optional_text(tags.get("opening_hours")),
            price_level=_price_level(tags),
            website=_website(tags),
        )

    def _remember_details(self, details: PlaceDetails) -> None:
        if len(self._details_cache) >= _DETAIL_CACHE_LIMIT and details.id not in self._details_cache:
            self._details_cache.pop(next(iter(self._details_cache)))
        self._details_cache[details.id] = details


def _as_search_result(details: PlaceDetails) -> PlaceSearchResult:
    return PlaceSearchResult(
        **details.model_dump(exclude={"opening_hours", "price_level", "website"})
    )


def _build_query(
    latitude: float,
    longitude: float,
    radius_m: int,
    selectors: Sequence[Tuple[str, str]],
    name_terms: Sequence[str],
    limit: int,
) -> str:
    name_filter = _name_filter(name_terms)
    clauses = [
        f'  nwr{_tag_filter(key, value)}{name_filter}(around:{radius_m},{latitude},{longitude});'
        for key, value in selectors
    ]
    body = "\n".join(clauses)
    return (
        f"[out:json][timeout:{_OVERPASS_QUERY_TIMEOUT_SECONDS}];\n"
        f"(\n{body}\n);\n"
        f"out center tags {limit};"
    )


def _tag_filter(key: str, value_regex: str) -> str:
    if not value_regex:
        return f'["{key}"]'
    return f'["{key}"~"{value_regex}"]'


def _name_filter(name_terms: Sequence[str]) -> str:
    if not name_terms:
        return ""
    pattern = "|".join(re.escape(term) for term in name_terms)
    return f'["name"~"{pattern}",i]'


def _search_terms(query: Optional[str]) -> Tuple[List[str], List[str]]:
    """Split a free-text query into ``(upstream name variants, canonical match terms)``.

    Vietnamese queries are matched with and without diacritics because OSM names appear
    both ways ("Bãi biển Mỹ Khê" vs "Bai bien My Khe"), while local filtering always
    compares accent-folded text so AND semantics stay stable.
    """
    variants: List[str] = []
    canonical: List[str] = []
    for raw in (query or "").casefold().split():
        token = "".join(char for char in raw if char.isalnum())[:_MAX_TERM_LENGTH]
        if len(token) < 2:
            continue
        folded = _fold_accents(token)
        if folded not in canonical:
            canonical.append(folded)
        for variant in (token, folded):
            if len(variant) >= 2 and variant not in variants:
                variants.append(variant)
        if len(canonical) >= _MAX_NAME_TERMS:
            break
    return variants, canonical


def _fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_marks.replace("đ", "d")


def _element_id(element: Dict[str, Any]) -> Optional[str]:
    element_type = str(element.get("type") or "")
    element_id = element.get("id")
    if element_type not in _ELEMENT_TYPES or not isinstance(element_id, int):
        return None
    return f"osm:{element_type}/{element_id}"


def _parse_place_id(place_id: str) -> Optional[Tuple[str, str]]:
    namespace, _, remainder = (place_id or "").partition(":")
    if namespace != "osm":
        return None
    element_type, _, element_id = remainder.partition("/")
    if element_type not in _ELEMENT_TYPES or not element_id.isdigit():
        return None
    return element_type, element_id


def _element_coords(element: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    latitude = element.get("lat")
    longitude = element.get("lon")
    if latitude is None or longitude is None:
        center = element.get("center")
        if isinstance(center, dict):
            latitude = center.get("lat")
            longitude = center.get("lon")
    try:
        return float(latitude), float(longitude)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
def _category_from_tags(tags: Dict[str, Any]) -> PlaceCategory:
    amenity = str(tags.get("amenity") or "").casefold()
    shop = str(tags.get("shop") or "").casefold()
    tourism = str(tags.get("tourism") or "").casefold()
    leisure = str(tags.get("leisure") or "").casefold()
    if amenity in _FOOD_AMENITY_VALUES or shop in _FOOD_SHOP_VALUES:
        return PlaceCategory.RESTAURANT
    if tourism in _LODGING_VALUES:
        return PlaceCategory.HOTEL
    if tourism in _ATTRACTION_TOURISM_VALUES or leisure in _ATTRACTION_LEISURE_VALUES:
        return PlaceCategory.ATTRACTION
    if tags.get("historic") or tags.get("man_made") or tags.get("place"):
        return PlaceCategory.LANDMARK
    return PlaceCategory.ATTRACTION


def _describe(tags: Dict[str, Any], destination: str) -> str:
    kind = ""
    for key in _KIND_TAG_KEYS:
        value = str(tags.get(key) or "").strip()
        if value:
            kind = value.replace("_", " ")
            break
    if not kind and tags.get("natural"):
        kind = str(tags["natural"]).replace("_", " ")
    kind = kind or "point of interest"
    cuisine = str(tags.get("cuisine") or "").strip()
    if cuisine:
        kind = f"{cuisine.replace(';', ',').replace('_', ' ')} {kind}"
    return f"{kind[:1].upper()}{kind[1:]} in {destination}"


def _city_from_tags(tags: Dict[str, Any]) -> str:
    for key in ("addr:city", "addr:town", "addr:village", "addr:municipality"):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return ""


def _address_from_tags(tags: Dict[str, Any]) -> str:
    street = " ".join(
        part
        for part in (
            str(tags.get("addr:housenumber") or "").strip(),
            str(tags.get("addr:street") or "").strip(),
        )
        if part
    )
    parts = (
        street,
        str(
            tags.get("addr:suburb")
            or tags.get("addr:ward")
            or tags.get("addr:district")
            or ""
        ).strip(),
        str(tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or "").strip(),
        str(tags.get("addr:postcode") or "").strip(),
    )
    return ", ".join(part for part in parts if part)


def _info_tags(tags: Dict[str, Any]) -> List[str]:
    """Emit planning keywords from OSM values, mirroring the mock provider convention."""
    collected: List[str] = []
    for key in _INFO_VALUE_KEYS:
        for token in _value_tokens(str(tags.get(key) or "")):
            if token not in collected:
                collected.append(token)
    for token in _value_tokens(str(tags.get("cuisine") or "")):
        if token not in collected:
            collected.append(token)
    if "beach" in collected and "beaches" not in collected:
        # Both spellings appear in traveller preferences and planner vocabularies.
        collected.append("beaches")
    return collected[:8]


def _value_tokens(value: str) -> List[str]:
    tokens: List[str] = []
    for raw in re.split(r"[;,]", value.casefold()):
        token = raw.strip().replace("_", " ")
        if token and token not in {"yes", "no", "unknown"} and token not in tokens:
            tokens.append(token)
    return tokens


def _price_level(tags: Dict[str, Any]) -> Optional[str]:
    fee = str(tags.get("fee") or "").strip().casefold()
    if fee == "no":
        return "low"
    if fee == "yes":
        return "medium"
    return None


def _website(tags: Dict[str, Any]) -> Optional[str]:
    for key in ("website", "contact:website", "url"):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return None


def _optional_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None
