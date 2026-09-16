"""Dependency injection for travel-data providers.

The agent and tools depend only on PlacesProvider / RouteProvider / WeatherProvider.
This factory chooses mock or live implementations from settings without leaking that
choice into the agent layer.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import Settings, get_settings
from app.knowledge.embeddings import build_embedding_provider
from app.knowledge.service import KnowledgeService
from app.knowledge.store import InMemoryKnowledgeStore
from app.providers.google import GooglePlacesProvider, GoogleRoutesProvider
from app.providers.mock import MockPlacesProvider, MockRouteProvider, MockWeatherProvider
from app.providers.mock.travel import MockFlightProvider, MockHotelProvider
from app.providers.open_meteo import OpenMeteoProvider
from app.providers.osm import NominatimGeocoder, OsmPlacesProvider, OsmRoutesProvider

logger = logging.getLogger(__name__)


def build_knowledge_service(settings: Optional[Settings] = None) -> KnowledgeService:
    cfg = settings or get_settings()
    embeddings = build_embedding_provider(
        api_key=cfg.openai_api_key,
        model=cfg.openai_embedding_model,
        dimensions=cfg.embedding_dimensions,
        force_hash=not bool(cfg.openai_api_key),
        timeout_seconds=cfg.llm_timeout_seconds,
        max_retries=cfg.llm_max_retries,
    )
    service = KnowledgeService(
        store=InMemoryKnowledgeStore(),
        embeddings=embeddings,
        knowledge_root=cfg.knowledge_root,
    )
    # Best-effort seed so the agent has contextual knowledge without a separate ops step.
    try:
        ingested = service.ingest_directory()
        logger.info("Seeded knowledge store with %s chunks from %s", ingested, cfg.knowledge_root)
    except Exception:  # noqa: BLE001
        logger.exception("Knowledge seed failed; continuing with empty store")
    return service


def _build_maps_providers(cfg: Settings):
    """Choose the places/routes adapters: Google (needs a key) or keyless OpenStreetMap.

    ``MAPS_PROVIDER=auto`` (default) prefers Google when a key exists and otherwise
    falls back to the keyless OSM stack, so live mode never silently degrades to mocks.
    """
    choice = (cfg.maps_provider or "auto").strip().lower()
    google_ready = bool(cfg.google_maps_api_key)

    if choice == "google" and not google_ready:
        logger.warning(
            "MAPS_PROVIDER=google but GOOGLE_MAPS_API_KEY is missing; using OpenStreetMap providers"
        )
    elif google_ready and choice in {"auto", "google"}:
        logger.info("Configured Google Places and Routes providers (maps_provider=%s)", choice)
        return (
            GooglePlacesProvider(
                cfg.google_maps_api_key,
                timeout_seconds=cfg.provider_http_timeout_seconds,
                max_retries=cfg.provider_http_max_retries,
                backoff_seconds=cfg.provider_http_backoff_seconds,
            ),
            GoogleRoutesProvider(
                cfg.google_maps_api_key,
                timeout_seconds=cfg.provider_http_timeout_seconds,
                max_retries=cfg.provider_http_max_retries,
                backoff_seconds=cfg.provider_http_backoff_seconds,
            ),
        )

    # One shared geocoder keeps the Nominatim cache warm and honours its 1 req/s policy.
    geocoder = NominatimGeocoder(
        base_url=cfg.osm_nominatim_url,
        user_agent=cfg.osm_user_agent,
        min_interval_seconds=cfg.osm_min_request_interval_seconds,
        timeout_seconds=cfg.provider_http_timeout_seconds,
        max_retries=cfg.provider_http_max_retries,
        backoff_seconds=cfg.provider_http_backoff_seconds,
    )
    logger.info(
        "Configured OpenStreetMap providers (Nominatim + Overpass + OSRM) maps_provider=%s",
        choice,
    )
    return (
        OsmPlacesProvider(
            overpass_url=cfg.osm_overpass_url,
            user_agent=cfg.osm_user_agent,
            geocoder=geocoder,
            search_radius_km=cfg.osm_search_radius_km,
            timeout_seconds=cfg.provider_http_timeout_seconds,
            max_retries=cfg.provider_http_max_retries,
            backoff_seconds=cfg.provider_http_backoff_seconds,
        ),
        OsmRoutesProvider(
            osrm_url=cfg.osm_osrm_url,
            user_agent=cfg.osm_user_agent,
            geocoder=geocoder,
            timeout_seconds=cfg.provider_http_timeout_seconds,
            max_retries=cfg.provider_http_max_retries,
            backoff_seconds=cfg.provider_http_backoff_seconds,
        ),
    )


def build_tool_dependencies(settings: Optional[Settings] = None):
    """Create tool dependencies from environment configuration."""
    from app.memory.service import MemoryService
    from app.tools.factory import ToolDependencies

    cfg = settings or get_settings()
    mode = (cfg.travel_data_mode or "mock").strip().lower()
    knowledge = build_knowledge_service(cfg)
    memory = MemoryService()

    if mode == "mock":
        logger.info("Using mock travel providers (travel_data_mode=mock)")
        return ToolDependencies(
            places=MockPlacesProvider(),
            weather=MockWeatherProvider(),
            routes=MockRouteProvider(),
            flights=MockFlightProvider(),
            hotels=MockHotelProvider(),
            knowledge=knowledge,
            memory=memory,
        )

    if mode != "live":
        logger.warning("Unknown travel_data_mode=%s; falling back to mocks", mode)
        return ToolDependencies(
            places=MockPlacesProvider(),
            weather=MockWeatherProvider(),
            routes=MockRouteProvider(),
            flights=MockFlightProvider(),
            hotels=MockHotelProvider(),
            knowledge=knowledge,
            memory=memory,
        )

    places, routes = _build_maps_providers(cfg)

    weather = OpenMeteoProvider(
        base_url=cfg.open_meteo_base_url,
        geocoding_url=cfg.open_meteo_geocoding_url,
        timeout_seconds=cfg.provider_http_timeout_seconds,
        max_retries=cfg.provider_http_max_retries,
        backoff_seconds=cfg.provider_http_backoff_seconds,
    )
    logger.info("Configured Open-Meteo weather provider base_url=%s", cfg.open_meteo_base_url)

    return ToolDependencies(
        places=places,
        weather=weather,
        routes=routes,
        knowledge=knowledge,
        memory=memory,
    )
