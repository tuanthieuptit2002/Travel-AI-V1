"""Build the safe LangChain tool set for future LangGraph agents.

Security constraints enforced here:
- No Python execution, shell, ORM session, or database engine tools.
- Database writes go only through TripService.save_trip_activity.
- Provider failures become generic structured errors without secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional, Sequence

from langchain_core.tools import BaseTool, StructuredTool

from app.providers.base import (
    FlightProvider,
    HotelProvider,
    PlacesProvider,
    RouteProvider,
    WeatherProvider,
)
from app.providers.mock import MockPlacesProvider, MockRouteProvider, MockWeatherProvider
from app.providers.mock.travel import MockFlightProvider, MockHotelProvider
from app.providers.models import (
    FlightSearchRequest,
    HotelSearchRequest,
    PlaceCategory,
    PlaceSearchRequest,
    PlaceSearchResult,
    RouteRequest,
    WeatherRequest,
)
from app.services.trip_service import SaveTripActivityCommand, TripBudgetSummary, TripService
from app.knowledge.service import KnowledgeService
from app.memory.service import MemoryService
from app.tools.safe import run_safely
from app.tools.schemas import (
    CalculateRouteInput,
    CalculateRouteOutput,
    GetTripBudgetInput,
    GetTripBudgetOutput,
    GetWeatherInput,
    GetWeatherOutput,
    KnowledgeCitationOut,
    PlaceDetailsInput,
    PlaceDetailsOutput,
    SaveTripActivityInput,
    SaveTripActivityOutput,
    SearchAttractionsInput,
    SearchAttractionsOutput,
    SearchFlightsInput,
    SearchFlightsOutput,
    SearchHotelsInput,
    SearchHotelsOutput,
    SearchPlacesInput,
    SearchPlacesOutput,
    SearchRestaurantsInput,
    SearchRestaurantsOutput,
    SearchTravelKnowledgeInput,
    SearchTravelKnowledgeOutput,
)

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "search_places",
        "get_place_details",
        "search_restaurants",
        "search_attractions",
        "search_hotels",
        "search_flights",
        "get_weather",
        "calculate_route",
        "get_trip_budget",
        "search_travel_knowledge",
        "retrieve_user_memory",
    }
)
WRITE_TOOL_NAMES: frozenset[str] = frozenset({"save_trip_activity", "update_user_memory"})
ALL_TOOL_NAMES: frozenset[str] = READ_ONLY_TOOL_NAMES | WRITE_TOOL_NAMES

_PRICE_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass
class ToolDependencies:
    """Explicit dependencies keep tools testable and prevent hidden SDK usage."""

    places: PlacesProvider
    weather: WeatherProvider
    routes: RouteProvider
    flights: Optional[FlightProvider] = None
    hotels: Optional[HotelProvider] = None
    trip_service: Optional[TripService] = None
    knowledge: Optional[KnowledgeService] = None
    memory: Optional[MemoryService] = None

    @classmethod
    def with_mocks(cls) -> ToolDependencies:
        return cls(
            places=MockPlacesProvider(),
            weather=MockWeatherProvider(),
            routes=MockRouteProvider(),
            flights=MockFlightProvider(),
            hotels=MockHotelProvider(),
            knowledge=KnowledgeService(),
            memory=MemoryService(),
        )

    @classmethod
    def from_settings(cls) -> ToolDependencies:
        """Build dependencies from environment (mock or live providers)."""
        from app.providers.factory import build_tool_dependencies

        return build_tool_dependencies()


def _haversine_km(lat_one: float, lon_one: float, lat_two: float, lon_two: float) -> float:
    latitude_delta = radians(lat_two - lat_one)
    longitude_delta = radians(lon_two - lon_one)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(lat_one)) * cos(radians(lat_two)) * sin(longitude_delta / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(value))


def _filter_places_by_radius(
    places: Sequence[PlaceSearchResult],
    latitude: Optional[float],
    longitude: Optional[float],
    radius_km: Optional[float],
) -> List[PlaceSearchResult]:
    if latitude is None or longitude is None:
        return list(places)
    maximum = radius_km if radius_km is not None else 25.0
    return [
        place
        for place in places
        if _haversine_km(latitude, longitude, place.latitude, place.longitude) <= maximum
    ]


def create_agent_tools(dependencies: Optional[ToolDependencies] = None) -> List[BaseTool]:
    """Create the complete, safe tool set for a future LangGraph graph."""
    deps = dependencies or ToolDependencies.with_mocks()

    def search_places(**kwargs: object) -> dict:
        request = SearchPlacesInput(**kwargs)

        def run() -> SearchPlacesOutput:
            places = deps.places.search_places(
                PlaceSearchRequest(destination=request.destination, query=request.query)
            )
            filtered = _filter_places_by_radius(
                places, request.latitude, request.longitude, request.radius_km
            )
            return SearchPlacesOutput(success=True, places=filtered)

        return run_safely(run, SearchPlacesOutput, "Unable to search places right now.")

    def get_place_details(**kwargs: object) -> dict:
        request = PlaceDetailsInput(**kwargs)

        def run() -> PlaceDetailsOutput:
            place = deps.places.get_place_details(request.place_id)
            if place is None:
                return PlaceDetailsOutput(success=False, error="Place was not found.")
            return PlaceDetailsOutput(success=True, place=place)

        return run_safely(run, PlaceDetailsOutput, "Unable to retrieve place details right now.")

    def search_restaurants(**kwargs: object) -> dict:
        request = SearchRestaurantsInput(**kwargs)

        def run() -> SearchRestaurantsOutput:
            matches = deps.places.search_places(
                PlaceSearchRequest(
                    destination=request.destination,
                    query=request.cuisine or "",
                    category=PlaceCategory.RESTAURANT,
                )
            )
            details = [deps.places.get_place_details(item.id) for item in matches]
            maximum_price = _PRICE_RANK.get(request.max_price_level or "high", 3)
            restaurants = [
                item
                for item in details
                if item is not None
                and (request.min_rating is None or (item.rating or 0) >= request.min_rating)
                and _PRICE_RANK.get(item.price_level or "high", 3) <= maximum_price
            ]
            return SearchRestaurantsOutput(success=True, restaurants=restaurants)

        return run_safely(run, SearchRestaurantsOutput, "Unable to search restaurants right now.")

    def search_attractions(**kwargs: object) -> dict:
        request = SearchAttractionsInput(**kwargs)

        def run() -> SearchAttractionsOutput:
            places = deps.places.search_places(
                PlaceSearchRequest(
                    destination=request.destination,
                    query=request.query,
                    category=PlaceCategory.ATTRACTION,
                )
            )
            attractions = [
                item
                for item in places
                if request.min_rating is None or (item.rating or 0) >= request.min_rating
            ]
            return SearchAttractionsOutput(success=True, attractions=attractions)

        return run_safely(run, SearchAttractionsOutput, "Unable to search attractions right now.")

    def search_hotels(**kwargs: object) -> dict:
        request = SearchHotelsInput(**kwargs)

        def run() -> SearchHotelsOutput:
            if deps.hotels is None:
                return SearchHotelsOutput(success=False, error="Hotel search is not configured.")
            hotels = deps.hotels.search_hotels(
                HotelSearchRequest(
                    destination=request.destination,
                    check_in=request.check_in,
                    check_out=request.check_out,
                    guests=request.guests,
                    rooms=request.rooms,
                    currency=request.currency.upper(),
                )
            )
            return SearchHotelsOutput(success=True, hotels=hotels)

        return run_safely(run, SearchHotelsOutput, "Unable to search hotels right now.")

    def search_flights(**kwargs: object) -> dict:
        request = SearchFlightsInput(**kwargs)

        def run() -> SearchFlightsOutput:
            if deps.flights is None:
                return SearchFlightsOutput(success=False, error="Flight search is not configured.")
            flights = deps.flights.search_flights(
                FlightSearchRequest(
                    origin=request.origin.upper(),
                    destination=request.destination.upper(),
                    departure_date=request.departure_date,
                    travelers=request.travelers,
                    currency=request.currency.upper(),
                )
            )
            return SearchFlightsOutput(success=True, flights=flights)

        return run_safely(run, SearchFlightsOutput, "Unable to search flights right now.")

    def get_weather(**kwargs: object) -> dict:
        request = GetWeatherInput(**kwargs)

        def run() -> GetWeatherOutput:
            from app.cache import cache_get, cache_key, cache_set
            from app.core.config import get_settings

            settings = get_settings()
            key = cache_key(
                "weather",
                request.destination,
                request.forecast_date.isoformat(),
            )
            if settings.cache_enabled:
                cached = cache_get(key)
                if cached is not None:
                    return GetWeatherOutput.model_validate(cached)
            weather = deps.weather.get_weather(
                WeatherRequest(destination=request.destination, forecast_date=request.forecast_date)
            )
            output = GetWeatherOutput(success=True, weather=weather)
            if settings.cache_enabled:
                cache_set(key, output.model_dump(mode="json"), settings.cache_weather_ttl_seconds)
            return output

        return run_safely(run, GetWeatherOutput, "Unable to retrieve weather right now.")

    def calculate_route(**kwargs: object) -> dict:
        request = CalculateRouteInput(**kwargs)

        def run() -> CalculateRouteOutput:
            # Pass opaque coordinate pairs; mock/live route providers interpret them.
            origin = f"{request.origin_latitude},{request.origin_longitude}"
            destination = (
                f"{request.destination_latitude},{request.destination_longitude}"
            )
            route = deps.routes.calculate_route(
                RouteRequest(
                    origin=origin,
                    destination=destination,
                    travel_mode=request.travel_mode,
                )
            )
            return CalculateRouteOutput(success=True, route=route)

        return run_safely(run, CalculateRouteOutput, "Unable to calculate route right now.")

    def get_trip_budget(**kwargs: object) -> dict:
        request = GetTripBudgetInput(**kwargs)

        def run() -> GetTripBudgetOutput:
            if deps.trip_service is None:
                return GetTripBudgetOutput(
                    success=False, error="Trip budget access is not configured."
                )
            summary: Optional[TripBudgetSummary] = deps.trip_service.get_budget(request.trip_id)
            if summary is None:
                return GetTripBudgetOutput(success=False, error="Trip was not found.")
            return GetTripBudgetOutput(
                success=True,
                trip_id=summary.trip_id,
                total_budget=summary.total_budget,
                scheduled_cost=summary.scheduled_cost,
                remaining_budget=summary.remaining_budget,
                currency=summary.currency,
            )

        return run_safely(run, GetTripBudgetOutput, "Unable to retrieve the trip budget right now.")

    def save_trip_activity(**kwargs: object) -> dict:
        request = SaveTripActivityInput(**kwargs)

        def run() -> SaveTripActivityOutput:
            if deps.trip_service is None:
                return SaveTripActivityOutput(
                    success=False, error="Trip activity saving is not configured."
                )
            activity = deps.trip_service.save_trip_activity(
                SaveTripActivityCommand(**request.model_dump())
            )
            return SaveTripActivityOutput(
                success=True,
                activity={
                    "id": str(activity.id),
                    "trip_day_id": str(activity.trip_day_id),
                    "place_id": str(activity.place_id) if activity.place_id else None,
                    "activity_type": activity.activity_type,
                    "order_index": activity.order_index,
                    "estimated_cost": (
                        str(activity.estimated_cost)
                        if activity.estimated_cost is not None
                        else None
                    ),
                },
            )

        return run_safely(run, SaveTripActivityOutput, "Unable to save the trip activity right now.")

    def search_travel_knowledge(**kwargs: object) -> dict:
        request = SearchTravelKnowledgeInput(**kwargs)

        def run() -> SearchTravelKnowledgeOutput:
            if deps.knowledge is None:
                return SearchTravelKnowledgeOutput(
                    success=False,
                    error="Travel knowledge search is not configured.",
                )
            hits = deps.knowledge.search(
                request.query,
                destination=request.destination,
                top_k=request.top_k,
            )
            results = [
                KnowledgeCitationOut(
                    title=hit.title,
                    source=hit.source,
                    destination=hit.destination,
                    category=hit.category,
                    score=hit.score,
                    excerpt=hit.content[:280],
                    citation=hit.citation,
                )
                for hit in hits
            ]
            return SearchTravelKnowledgeOutput(success=True, results=results)

        return run_safely(
            run,
            SearchTravelKnowledgeOutput,
            "Unable to search travel knowledge right now.",
        )

    definitions = [
        (
            "search_places",
            (
                "Search normalized attractions, landmarks, restaurants, or hotels in a "
                "destination. Optional latitude, longitude, and radius_km restrict results "
                "to a geographic area. Returns no provider-native payloads."
            ),
            SearchPlacesInput,
            search_places,
        ),
        (
            "get_place_details",
            (
                "Get normalized details for a TripMind place ID previously returned by "
                "search_places. Returns no provider-native response fields."
            ),
            PlaceDetailsInput,
            get_place_details,
        ),
        (
            "search_restaurants",
            (
                "Find normalized restaurant recommendations by destination, optional cuisine, "
                "minimum rating, and maximum price level (low, medium, or high)."
            ),
            SearchRestaurantsInput,
            search_restaurants,
        ),
        (
            "search_attractions",
            (
                "Find normalized attractions in a destination, optionally matching a query "
                "and minimum rating."
            ),
            SearchAttractionsInput,
            search_attractions,
        ),
        (
            "search_hotels",
            (
                "Search normalized hotel offers for dates and guest counts through a configured "
                "hotel provider. Returns a safe unavailable result when no provider is configured."
            ),
            SearchHotelsInput,
            search_hotels,
        ),
        (
            "search_flights",
            (
                "Search normalized flight offers through a configured flight provider. "
                "Returns a safe unavailable result when no provider is configured."
            ),
            SearchFlightsInput,
            search_flights,
        ),
        (
            "get_weather",
            (
                "Get a normalized daily weather forecast for a destination and ISO date. "
                "Provider errors are converted to a safe structured result."
            ),
            GetWeatherInput,
            get_weather,
        ),
        (
            "calculate_route",
            (
                "Calculate an estimated route from origin and destination coordinates with a "
                "selected travel mode (driving, walking, bicycling, or transit)."
            ),
            CalculateRouteInput,
            calculate_route,
        ),
        (
            "get_trip_budget",
            (
                "Read the saved trip budget and scheduled activity costs through the controlled "
                "TripService. This read-only tool does not expose database access."
            ),
            GetTripBudgetInput,
            get_trip_budget,
        ),
        (
            "save_trip_activity",
            (
                "Save one validated trip activity through the controlled TripService. This is "
                "the only write tool and it cannot execute arbitrary database commands."
            ),
            SaveTripActivityInput,
            save_trip_activity,
        ),
        (
            "search_travel_knowledge",
            (
                "Retrieve curated Vietnam travel knowledge (destination guides, food, customs, "
                "safety, seasonal tips, transportation advice) with citations. "
                "Do not use this tool for live weather, live flights, or live traffic/routes. "
                "Do not use this tool for per-user preferences — use retrieve_user_memory instead."
            ),
            SearchTravelKnowledgeInput,
            search_travel_knowledge,
        ),
    ]
    tools = [
        StructuredTool.from_function(
            func=func,
            name=name,
            description=description,
            args_schema=schema,
        )
        for name, description, schema, func in definitions
    ]
    from app.memory.tools import MemoryRetrievalTool, MemoryUpdateTool

    memory_service = (dependencies.memory if dependencies else None) or MemoryService()
    tools.append(MemoryRetrievalTool(memory_service).as_langchain_tool())
    tools.append(MemoryUpdateTool(memory_service).as_langchain_tool())
    return tools


def create_read_only_tools(dependencies: Optional[ToolDependencies] = None) -> List[BaseTool]:
    """Return only read tools for agents that must not mutate trip data."""
    return [tool for tool in create_agent_tools(dependencies) if tool.name in READ_ONLY_TOOL_NAMES]


def create_write_tools(dependencies: Optional[ToolDependencies] = None) -> List[BaseTool]:
    """Return only controlled write tools (save_trip_activity, update_user_memory)."""
    return [tool for tool in create_agent_tools(dependencies) if tool.name in WRITE_TOOL_NAMES]
