"""Live probe: exercise OSM providers against public endpoints (manual check, keyless).

Usage (backend venv):
    PYTHONPATH=. .venv/bin/python scripts/check_osm_live.py
"""

from __future__ import annotations

import logging
import time

from app.core.config import Settings
from app.providers.models import PlaceSearchRequest, RouteRequest, TravelMode
from app.providers.osm import NominatimGeocoder, OsmPlacesProvider, OsmRoutesProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("osm_live_probe")

settings = Settings(travel_data_mode="live", maps_provider="osm", google_maps_api_key="")
logger.info("maps_provider=%s travel_data_mode=%s", settings.maps_provider, settings.travel_data_mode)

geocoder = NominatimGeocoder(
    base_url=settings.osm_nominatim_url,
    user_agent=settings.osm_user_agent,
    min_interval_seconds=settings.osm_min_request_interval_seconds,
    timeout_seconds=15.0,
)
places = OsmPlacesProvider(
    overpass_url=settings.osm_overpass_url,
    user_agent=settings.osm_user_agent,
    geocoder=geocoder,
    search_radius_km=settings.osm_search_radius_km,
    timeout_seconds=15.0,
)
routes = OsmRoutesProvider(
    osrm_url=settings.osm_osrm_url,
    user_agent=settings.osm_user_agent,
    geocoder=geocoder,
    timeout_seconds=15.0,
)

started = time.perf_counter()
hit = geocoder.geocode("Da Nang")
logger.info("geocode Da Nang -> %s", hit)
time.sleep(1)

hits = places.search_places(
    PlaceSearchRequest(destination="Da Nang", query="beach", limit=5)
)
for item in hits:
    logger.info("place: %s | %s | %.4f,%.4f | %s", item.name, item.category, item.latitude, item.longitude, item.id)
time.sleep(1)

if hits:
    detail = places.get_place_details(hits[0].id)
    logger.info("detail: %s | %s | %s", detail and detail.name, detail and detail.opening_hours, detail and detail.website)
    time.sleep(1)

route = routes.calculate_route(
    RouteRequest(origin="16.0544,108.2022", destination="16.0611,108.2270", travel_mode=TravelMode.DRIVING)
)
logger.info("route: %s km, %s min (%s)", route.distance_km, route.duration_minutes, route.travel_mode)
logger.info("probe finished in %.1fs", time.perf_counter() - started)
