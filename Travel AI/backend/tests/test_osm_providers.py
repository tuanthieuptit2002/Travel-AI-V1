"""Contract tests for the keyless OpenStreetMap providers (Nominatim/Overpass/OSRM)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.errors import ProviderError
from app.providers.factory import build_tool_dependencies
from app.providers.google import GooglePlacesProvider
from app.providers.http import ProviderHttpClient
from app.providers.models import PlaceCategory, PlaceSearchRequest, RouteRequest, TravelMode
from app.providers.osm import NominatimGeocoder, OsmPlacesProvider, OsmRoutesProvider

_NOMINATIM_HIT: Dict[str, Any] = {
    "lat": "16.0544",
    "lon": "108.2022",
    "name": "Da Nang",
    "display_name": "Da Nang, Vietnam",
    "address": {"city": "Da Nang"},
}

_OVERPASS_ELEMENTS: List[Dict[str, Any]] = [
    {
        "type": "node",
        "id": 1,
        "lat": 16.05,
        "lon": 108.24,
        "tags": {
            "amenity": "restaurant",
            "name": "Banh Xeo Ba Duong",
            "cuisine": "vietnamese",
            "addr:housenumber": "12",
            "addr:street": "Hoang Dieu",
            "addr:city": "Da Nang",
        },
    },
    {
        "type": "way",
        "id": 2,
        "center": {"lat": 16.0611, "lon": 108.2270},
        "tags": {"tourism": "attraction", "name": "Dragon Bridge", "fee": "no"},
    },
    {
        "type": "node",
        "id": 3,
        "lat": 16.07,
        "lon": 108.23,
        "tags": {"amenity": "cafe", "name": "Cong Cafe"},
    },
    {
        "type": "way",
        "id": 4,
        "center": {"lat": 16.05, "lon": 108.25},
        "tags": {"tourism": "hotel", "name": "Furama Resort"},
    },
]

_DETAIL_ELEMENT: Dict[str, Any] = {
    "type": "way",
    "id": 123456,
    "center": {"lat": 16.0611, "lon": 108.2270},
    "tags": {
        "tourism": "attraction",
        "name": "Dragon Bridge",
        "opening_hours": "24/7",
        "fee": "no",
        "website": "https://dragonbridge.example",
        "addr:housenumber": "1",
        "addr:street": "Nguyen Van Linh",
        "addr:district": "Hai Chau",
        "addr:city": "Da Nang",
    },
}


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def _http(
    handler: Callable[[httpx.Request], httpx.Response], *, provider: str = "osm_test"
) -> ProviderHttpClient:
    return ProviderHttpClient(
        provider=provider, max_retries=0, backoff_seconds=0, client=_mock_client(handler)
    )


def _handler(
    calls: List[httpx.Request],
    *,
    search_payload: Optional[List[Dict[str, Any]]] = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Route Nominatim, Overpass and OSRM calls of a single mock transport."""

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/search"):
            payload = [_NOMINATIM_HIT] if search_payload is None else search_payload
            return httpx.Response(200, json=payload)
        if path.endswith("/interpreter"):
            data = httpx.QueryParams(request.url.query).get("data") or ""
            if "way(123456)" in data:
                return httpx.Response(200, json={"elements": [_DETAIL_ELEMENT]})
            return httpx.Response(200, json={"elements": _OVERPASS_ELEMENTS})
        if "/route/v1/" in path:
            return httpx.Response(
                200, json={"code": "Ok", "routes": [{"distance": 12999.5, "duration": 968.5}]}
            )
        return httpx.Response(404, json={})

    return handle


def _places_provider(
    calls: List[httpx.Request],
    *,
    search_payload: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> OsmPlacesProvider:
    return OsmPlacesProvider(
        http_client=_http(_handler(calls, search_payload=search_payload)),
        min_interval_seconds=0.0,
        timeout_seconds=1.0,
        max_retries=0,
        **kwargs,
    )


def _route_provider(calls: List[httpx.Request], **kwargs: Any) -> OsmRoutesProvider:
    return OsmRoutesProvider(
        http_client=_http(_handler(calls)),
        min_interval_seconds=0.0,
        timeout_seconds=1.0,
        max_retries=0,
        **kwargs,
    )


def test_maps_provider_setting_must_be_known() -> None:
    with pytest.raises(ValidationError):
        Settings(maps_provider="bing")


def test_live_mode_with_google_choice_still_requires_key() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            travel_data_mode="live",
            maps_provider="google",
            google_maps_api_key="",
            secret_key="unit-test-secret-key-32-characters-min",
            api_keys="unit-test-api-key",
        )
    # Keyless OSM is the documented way to run live mode without Google credentials.
    settings = Settings(
        app_env="production",
        travel_data_mode="live",
        maps_provider="osm",
        secret_key="unit-test-secret-key-32-characters-min",
        api_keys="unit-test-api-key",
    )
    assert settings.maps_provider == "osm"
    assert settings.google_maps_api_key == ""


def test_geocoder_throttles_nominatim_and_caches_hits() -> None:
    calls: List[httpx.Request] = []
    geocoder = NominatimGeocoder(
        http_client=_http(_handler(calls)),
        min_interval_seconds=0.0,
        max_retries=0,
    )
    first = geocoder.geocode("Da Nang")
    second = geocoder.geocode("  da nang ")
    assert first == (16.0544, 108.2022, "Da Nang")
    assert second == first
    assert len(calls) == 1, "cached lookups must not hit Nominatim twice"
    assert calls[0].headers["user-agent"].startswith("TripMindAI"), "policy requires a User-Agent"


def test_geocoder_returns_none_when_nominatim_has_no_match() -> None:
    geocoder = NominatimGeocoder(
        http_client=_http(_handler([], search_payload=[])),
        min_interval_seconds=0.0,
        max_retries=0,
    )
    assert geocoder.geocode("Nowhere At All") is None
    assert geocoder.geocode("   ") is None


def test_geocoder_reverse_geocoding() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/reverse")
        return httpx.Response(200, json={"display_name": "12 Hoang Dieu, Da Nang, Vietnam"})

    geocoder = NominatimGeocoder(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    assert geocoder.reverse(16.05, 108.24) == "12 Hoang Dieu, Da Nang, Vietnam"


def test_places_search_geocodes_destination_and_queries_overpass() -> None:
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    results = provider.search_places(
        PlaceSearchRequest(destination="Da Nang", category=PlaceCategory.ATTRACTION, limit=5)
    )
    assert [r.name for r in results] == ["Dragon Bridge"]
    assert results[0].id == "osm:way/2"
    assert results[0].category is PlaceCategory.ATTRACTION
    assert results[0].destination == "Da Nang"
    assert results[0].latitude == pytest.approx(16.0611)
    assert results[0].longitude == pytest.approx(108.2270)

    interpreter = [c for c in calls if c.url.path.endswith("/interpreter")]
    assert len(interpreter) == 1, "category search should issue one Overpass query"
    query = httpx.QueryParams(interpreter[0].url.query).get("data") or ""
    assert "around:" in query and "out center tags" in query
    assert '"tourism"~"^(attraction|museum' in query
    # Tags follow the planner vocabulary (plain keywords), not raw OSM "key=value".
    assert "attraction" in results[0].tags


def test_places_search_name_filter_then_category_fallback() -> None:
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    results = provider.search_places(PlaceSearchRequest(destination="Da Nang", query="cafe dragon"))
    assert {r.name for r in results} == {"Cong Cafe", "Dragon Bridge"}
    interpreter = [c for c in calls if c.url.path.endswith("/interpreter")]
    assert len(interpreter) == 2, "an over-narrow name filter must be retried without it"
    assert '"name"~"cafe|dragon"' in (httpx.QueryParams(interpreter[0].url.query).get("data") or "")
    assert '"name"' not in (httpx.QueryParams(interpreter[1].url.query).get("data") or "")


def test_places_search_without_category_maps_osm_tags_to_categories() -> None:
    provider = _places_provider([])
    results = provider.search_places(PlaceSearchRequest(destination="Da Nang"))
    categories = {r.name: r.category for r in results}
    assert categories["Banh Xeo Ba Duong"] is PlaceCategory.RESTAURANT
    assert categories["Dragon Bridge"] is PlaceCategory.ATTRACTION
    assert categories["Furama Resort"] is PlaceCategory.HOTEL


def test_places_search_vietnamese_query_matches_unaccented_osm_names() -> None:
    accents: List[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        accents.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=[_NOMINATIM_HIT])
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "way",
                        "id": 7,
                        "center": {"lat": 16.05, "lon": 108.24},
                        "tags": {"tourism": "attraction", "name": "Bai bien My Khe"},
                    }
                ]
            },
        )

    provider = OsmPlacesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    results = provider.search_places(
        PlaceSearchRequest(destination="Đà Nẵng", query="bãi biển mỹ khê")
    )
    assert [r.name for r in results] == ["Bai bien My Khe"]
    interpreter = [c for c in accents if c.url.path.endswith("/interpreter")]
    query = httpx.QueryParams(interpreter[0].url.query).get("data") or ""
    assert "bãi" in query, "accented variants keep native OSM names reachable"


def test_places_search_requires_some_location_hint() -> None:
    provider = _places_provider([])
    with pytest.raises(ProviderError) as excinfo:
        provider.search_places(PlaceSearchRequest())
    assert excinfo.value.code == "invalid_request"

    # Without a destination the query itself is geocoded, which keeps chat-style
    # requests such as "banh xeo in Da Nang" working.
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    results = provider.search_places(PlaceSearchRequest(query="Da Nang"))
    assert results
    assert [c for c in calls if c.url.path.endswith("/search")]


def test_places_search_surfaces_unknown_destination() -> None:
    provider = _places_provider([], search_payload=[])
    with pytest.raises(ProviderError) as excinfo:
        provider.search_places(PlaceSearchRequest(destination="Atlantis"))
    assert excinfo.value.provider == "nominatim"
    assert excinfo.value.code == "geocode_not_found"


def test_places_search_accepts_coordinates_without_geocoding() -> None:
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    provider.search_places(
        PlaceSearchRequest(destination="16.0544,108.2022", category=PlaceCategory.HOTEL)
    )
    assert not [c for c in calls if c.url.path.endswith("/search")], "no geocode call expected"
    interpreter = [c for c in calls if c.url.path.endswith("/interpreter")]
    query = httpx.QueryParams(interpreter[0].url.query).get("data") or ""
    assert "(around:12000,16.0544,108.2022)" in query


def test_places_search_returns_empty_list_when_overpass_has_no_elements() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=[_NOMINATIM_HIT])
        return httpx.Response(200, json={"elements": [], "remark": "runtime error"})

    provider = OsmPlacesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    assert provider.search_places(PlaceSearchRequest(destination="Da Nang")) == []


def test_get_place_details_parses_osm_id_and_reuses_cache() -> None:
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    details = provider.get_place_details("osm:way/123456")
    assert details is not None
    assert details.id == "osm:way/123456"
    assert details.name == "Dragon Bridge"
    assert details.category is PlaceCategory.ATTRACTION
    assert details.opening_hours == "24/7"
    assert details.price_level == "low"
    assert details.website == "https://dragonbridge.example"
    assert details.address == "1 Nguyen Van Linh, Hai Chau, Da Nang"
    assert "attraction" in details.tags
    assert "beach" not in details.tags
    assert provider.get_place_details("osm:way/123456") == details
    assert len([c for c in calls if c.url.path.endswith("/interpreter")]) == 1


def test_get_place_details_rejects_foreign_identifiers() -> None:
    calls: List[httpx.Request] = []
    provider = _places_provider(calls)
    assert provider.get_place_details("places/abc123") is None
    assert provider.get_place_details("") is None
    assert calls == []


def test_get_place_details_returns_none_when_overpass_is_empty() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": []})

    provider = OsmPlacesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    assert provider.get_place_details("osm:node/999") is None


def test_routes_provider_computes_driving_route_from_coordinates() -> None:
    calls: List[httpx.Request] = []
    provider = _route_provider(calls)
    result = provider.calculate_route(
        RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270")
    )
    assert result.travel_mode is TravelMode.DRIVING
    assert result.distance_km == 13.0
    assert result.duration_minutes == 16
    route_calls = [c for c in calls if "/route/v1/" in c.url.path]
    assert len(route_calls) == 1
    assert route_calls[0].url.path.endswith("/route/v1/driving/108.2022,16.0544;108.227,16.0611")
    assert not [c for c in calls if c.url.path.endswith("/search")]


def test_routes_provider_downgrades_to_http_when_https_transport_fails() -> None:
    calls: List[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.scheme == "https":
            raise httpx.ConnectError("TLS handshake failure")
        return httpx.Response(
            200, json={"code": "Ok", "routes": [{"distance": 12999.5, "duration": 968.5}]}
        )

    provider = OsmRoutesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, timeout_seconds=1.0, max_retries=0
    )
    result = provider.calculate_route(
        RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270")
    )
    assert result.distance_km == 13.0
    schemes = [c.url.scheme for c in calls if "/route/v1/" in c.url.path]
    assert schemes == ["https", "http"]
    # The downgrade is sticky: a second call goes straight to http.
    provider.calculate_route(
        RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270")
    )
    schemes = [c.url.scheme for c in calls if "/route/v1/" in c.url.path]
    assert schemes == ["https", "http", "http"]


def test_routes_provider_maps_travel_modes_to_osrm_profiles() -> None:
    for mode, profile in (
        (TravelMode.WALKING, "foot"),
        (TravelMode.BICYCLING, "bike"),
    ):
        calls: List[httpx.Request] = []
        provider = _route_provider(calls)
        provider.calculate_route(
            RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270", travel_mode=mode)
        )
        assert f"/route/v1/{profile}/" in calls[0].url.path


def test_routes_provider_geocodes_named_waypoints() -> None:
    calls: List[httpx.Request] = []
    provider = _route_provider(calls)
    provider.calculate_route(RouteRequest(origin="Da Nang", destination="16.0611,108.2270"))
    assert len([c for c in calls if c.url.path.endswith("/search")]) == 1
    assert len([c for c in calls if "/route/v1/" in c.url.path]) == 1


def test_routes_provider_short_circuits_identical_points() -> None:
    calls: List[httpx.Request] = []
    provider = _route_provider(calls)
    result = provider.calculate_route(
        RouteRequest(origin="16.0544,108.2022", destination="16.0544,108.2022")
    )
    assert result.distance_km == 0
    assert result.duration_minutes == 0
    assert calls == [], "identical waypoints must not call OSRM"


def test_routes_provider_rejects_transit_mode() -> None:
    provider = _route_provider([])
    with pytest.raises(ProviderError) as excinfo:
        provider.calculate_route(
            RouteRequest(
                origin="16.0544,108.2022",
                destination="16.0611,108.2270",
                travel_mode=TravelMode.TRANSIT,
            )
        )
    assert excinfo.value.code == "unsupported_travel_mode"


def test_routes_provider_reports_unroutable_pairs() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "NoRoute", "routes": []})

    provider = OsmRoutesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    with pytest.raises(ProviderError) as excinfo:
        provider.calculate_route(
            RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270")
        )
    assert excinfo.value.code == "not_found"
    assert excinfo.value.status_code == 404


def test_routes_provider_raises_when_waypoint_cannot_be_geocoded() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"code": "Ok", "routes": []})

    provider = OsmRoutesProvider(
        http_client=_http(handle), min_interval_seconds=0.0, max_retries=0
    )
    with pytest.raises(ProviderError) as excinfo:
        provider.calculate_route(RouteRequest(origin="Atlantis", destination="16.0611,108.2270"))
    assert excinfo.value.code == "geocode_not_found"


def test_build_tool_dependencies_prefers_google_when_key_is_present() -> None:
    deps = build_tool_dependencies(
        Settings(travel_data_mode="live", maps_provider="auto", google_maps_api_key="test-key")
    )
    assert isinstance(deps.places, GooglePlacesProvider)
    assert not isinstance(deps.places, OsmPlacesProvider)


def test_build_tool_dependencies_can_force_osm_even_with_google_key() -> None:
    deps = build_tool_dependencies(
        Settings(travel_data_mode="live", maps_provider="osm", google_maps_api_key="test-key")
    )
    assert isinstance(deps.places, OsmPlacesProvider)
    assert isinstance(deps.routes, OsmRoutesProvider)


def test_build_tool_dependencies_mock_mode_stays_offline() -> None:
    deps = build_tool_dependencies(Settings(travel_data_mode="mock", maps_provider="auto"))
    assert not isinstance(deps.places, OsmPlacesProvider)
    assert not isinstance(deps.places, GooglePlacesProvider)