"""LangGraph node functions for the TripMind travel agent."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.agent.models import FinalTravelResponse, TripItinerary
from app.agent.optimization import BudgetAgent, ItineraryOptimizer
from app.agent.parser import DeterministicRequestParser, RequestParser
from app.agent.planner import build_grounded_itinerary, iso_to_date
from app.agent.state import TravelAgentState
from app.agent.validator import known_ids_from_candidates, validate_itinerary
from app.memory.models import UserMemory
from app.tools import ToolDependencies, create_agent_tools


class TravelAgentContext:
    """Shared runtime dependencies injected into graph nodes."""

    def __init__(
        self,
        *,
        tools: Optional[Dict[str, Any]] = None,
        parser: Optional[RequestParser] = None,
        reference_date: Optional[date] = None,
        dependencies: Optional[ToolDependencies] = None,
    ) -> None:
        self.dependencies = dependencies or ToolDependencies.with_mocks()
        if tools is None:
            from app.tools.limits import wrap_tools_with_limits

            raw = {tool.name: tool for tool in create_agent_tools(self.dependencies)}
            self.tools = wrap_tools_with_limits(raw)
        else:
            self.tools = tools
        self.parser = parser or DeterministicRequestParser()
        self.reference_date = reference_date or date(2026, 10, 12)


def parse_request(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    try:
        parsed = ctx.parser.parse(state["user_request"], reference_date=ctx.reference_date)
    except Exception as exc:  # noqa: BLE001 - convert to state error for the graph
        return {
            "parse_error": str(exc),
            "validation_errors": [f"Không phân tích được yêu cầu du lịch: {exc}"],
            "preferences": [],
            "candidate_places": [],
            "candidate_restaurants": [],
            "candidate_hotels": [],
            "candidate_flights": [],
            "optimization_notes": [],
            "budget_breakdown": None,
        }

    return {
        "destination": parsed.destination,
        "origin": parsed.origin,
        "start_date": parsed.start_date.isoformat(),
        "end_date": parsed.end_date.isoformat(),
        "travelers": parsed.travelers,
        "budget": str(parsed.budget_total),
        "currency": parsed.currency,
        "preferences": parsed.preferences,
        "parse_error": None,
        "validation_errors": [],
        "candidate_places": [],
        "candidate_restaurants": [],
        "candidate_hotels": [],
        "candidate_flights": [],
        "weather": [],
        "routes": [],
        "knowledge_hits": [],
        "citations": [],
        "itinerary": None,
        "final_response": None,
        "user_memory": None,
        "memory_updates": [],
        "optimization_notes": [],
        "budget_breakdown": None,
    }


def retrieve_memory(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    """Load structured long-term preferences before planning. Separate from RAG."""
    user_id = state.get("user_id")
    if not user_id:
        return {"user_memory": None}

    tool = ctx.tools.get("retrieve_user_memory")
    if tool is None:
        return {"user_memory": None}

    result = tool.invoke({"user_id": user_id})
    if not result.get("success") or not result.get("memory"):
        return {"user_memory": None}

    memory = UserMemory.model_validate(result["memory"])
    existing = list(state.get("preferences") or [])
    merged = list(dict.fromkeys([*existing, *memory.as_planning_hints()]))
    disliked = {item.casefold() for item in memory.disliked_activities}
    if disliked:
        merged = [pref for pref in merged if pref.casefold() not in disliked]

    return {
        "user_memory": memory.model_dump(mode="json"),
        "preferences": merged,
    }


def gather_places(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    if state.get("parse_error") or not state.get("destination"):
        return {"candidate_places": []}

    destination = state["destination"]
    preferences = state.get("preferences") or []
    tool = ctx.tools["search_attractions"]
    details_tool = ctx.tools["get_place_details"]
    search_tool = ctx.tools["search_places"]

    collected: Dict[str, Dict[str, Any]] = {}
    queries = preferences or [""]
    for query in queries:
        for result in (
            tool.invoke({"destination": destination, "query": query, "min_rating": 0}),
            search_tool.invoke({"destination": destination, "query": query}),
        ):
            if not result.get("success"):
                continue
            items = result.get("attractions") or result.get("places") or []
            for item in items:
                details = details_tool.invoke({"place_id": item["id"]})
                if details.get("success") and details.get("place"):
                    place = details["place"]
                    if place.get("category") != "restaurant":
                        collected[place["id"]] = place

    # Broad destination fill so multi-day plans have enough catalog depth.
    broad = search_tool.invoke({"destination": destination, "query": ""})
    if broad.get("success"):
        for item in broad.get("places") or []:
            if item["id"] in collected:
                continue
            details = details_tool.invoke({"place_id": item["id"]})
            if details.get("success") and details.get("place"):
                place = details["place"]
                if place.get("category") != "restaurant":
                    collected[place["id"]] = place

    return {"candidate_places": list(collected.values())}


def gather_restaurants(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    if state.get("parse_error") or not state.get("destination"):
        return {"candidate_restaurants": []}

    destination = state["destination"]
    preferences = state.get("preferences") or []
    cuisine_hints = [
        pref for pref in preferences if pref in {"local food", "seafood", "cafe", "banh mi"}
    ] or [None]
    tool = ctx.tools["search_restaurants"]
    collected: Dict[str, Dict[str, Any]] = {}
    for cuisine in cuisine_hints:
        payload: Dict[str, Any] = {"destination": destination}
        if cuisine:
            payload["cuisine"] = cuisine
        result = tool.invoke(payload)
        if not result.get("success"):
            continue
        for restaurant in result.get("restaurants") or []:
            collected[restaurant["id"]] = restaurant

    return {"candidate_restaurants": list(collected.values())}


def gather_weather(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    if state.get("parse_error") or not state.get("destination"):
        return {"weather": []}

    start = iso_to_date(state["start_date"])  # type: ignore[arg-type]
    end = iso_to_date(state["end_date"])  # type: ignore[arg-type]
    tool = ctx.tools["get_weather"]
    forecasts: List[Dict[str, Any]] = []
    day = start
    while day <= end:
        result = tool.invoke(
            {"destination": state["destination"], "forecast_date": day.isoformat()}
        )
        if result.get("success") and result.get("weather"):
            forecasts.append(result["weather"])
        day += timedelta(days=1)
    return {"weather": forecasts}


def gather_knowledge(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    """Retrieve contextual destination knowledge via RAG (not live weather/flights/routes)."""
    if state.get("parse_error") or not state.get("destination"):
        return {"knowledge_hits": [], "citations": []}

    tool = ctx.tools.get("search_travel_knowledge")
    if tool is None:
        return {"knowledge_hits": [], "citations": []}

    destination = state["destination"]
    preferences = state.get("preferences") or []
    preference_text = ", ".join(preferences) if preferences else "general travel tips"
    query = (
        f"Travel advice for {destination}: local customs, food, transportation, "
        f"seasonal tips, and safety for visitors interested in {preference_text}."
    )
    result = tool.invoke({"query": query, "destination": destination, "top_k": 5})
    if not result.get("success"):
        return {"knowledge_hits": [], "citations": []}

    hits = result.get("results") or []
    citations = [item.get("citation") or item.get("source") for item in hits if item]
    return {"knowledge_hits": hits, "citations": [item for item in citations if item]}


def generate_itinerary(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    if state.get("parse_error"):
        return {"itinerary": None}

    itinerary = build_grounded_itinerary(
        destination=state["destination"] or "",
        origin=state.get("origin"),
        start_date=iso_to_date(state["start_date"]),  # type: ignore[arg-type]
        end_date=iso_to_date(state["end_date"]),  # type: ignore[arg-type]
        travelers=int(state.get("travelers") or 1),
        total_budget=Decimal(state.get("budget") or "0"),
        currency=state.get("currency") or "VND",
        preferences=state.get("preferences") or [],
        candidate_places=state.get("candidate_places") or [],
        candidate_restaurants=state.get("candidate_restaurants") or [],
    )

    routes: List[Dict[str, Any]] = []
    for day in itinerary.days:
        previous = None
        for activity in day.activities:
            if previous is not None:
                routes.append(
                    {
                        "day_number": day.day_number,
                        "from_place_id": previous.place_id,
                        "to_place_id": activity.place_id,
                        "travel_time_minutes": activity.travel_time_from_previous,
                    }
                )
            previous = activity

    return {
        "itinerary": itinerary.model_dump(mode="json"),
        "routes": routes,
    }


def validate_itinerary_node(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    if state.get("parse_error"):
        return {"validation_errors": list(state.get("validation_errors") or [])}

    raw = state.get("itinerary")
    if not raw:
        return {"validation_errors": ["Thiếu lịch trình."]}

    itinerary = TripItinerary.model_validate(raw)
    errors = validate_itinerary(
        itinerary,
        known_place_ids=known_ids_from_candidates(
            state.get("candidate_places") or [],
            state.get("candidate_restaurants") or [],
            state.get("candidate_hotels") or [],
        ),
        require_weather=True,
        weather_available=bool(state.get("weather")),
    )
    return {"validation_errors": errors}


def optimize_itinerary(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    """Dedicated optimization stage: budget, distance, hours, weather, pace, duplicates."""
    if state.get("parse_error"):
        return {
            "optimization_notes": [],
            "budget_breakdown": None,
            "candidate_hotels": state.get("candidate_hotels") or [],
            "candidate_flights": state.get("candidate_flights") or [],
        }

    raw = state.get("itinerary")
    if not raw:
        return {"optimization_notes": ["Không có lịch trình để tối ưu."]}

    itinerary = TripItinerary.model_validate(raw)
    hotels = list(state.get("candidate_hotels") or [])
    flights = list(state.get("candidate_flights") or [])

    # Gather lodging/transport offers when tools are available.
    hotels_tool = ctx.tools.get("search_hotels")
    if hotels_tool and not hotels and state.get("destination") and state.get("start_date") and state.get("end_date"):
        result = hotels_tool.invoke(
            {
                "destination": state["destination"],
                "check_in": state["start_date"],
                "check_out": state["end_date"],
                "guests": int(state.get("travelers") or 1),
                "currency": state.get("currency") or "VND",
            }
        )
        if result.get("success"):
            hotels = list(result.get("hotels") or [])

    flights_tool = ctx.tools.get("search_flights")
    origin = state.get("origin")
    if flights_tool and not flights and origin and state.get("destination") and state.get("start_date"):
        # Use compact airport-style codes when origin/destination look like cities.
        origin_code = _airport_hint(origin)
        dest_code = _airport_hint(state["destination"])
        result = flights_tool.invoke(
            {
                "origin": origin_code,
                "destination": dest_code,
                "departure_date": state["start_date"],
                "travelers": int(state.get("travelers") or 1),
                "currency": state.get("currency") or "VND",
            }
        )
        if result.get("success"):
            flights = list(result.get("flights") or [])

    trip_pace = None
    memory_raw = state.get("user_memory")
    if memory_raw:
        trip_pace = memory_raw.get("preferred_trip_pace")

    optimizer = ItineraryOptimizer(BudgetAgent())
    result = optimizer.optimize(
        itinerary,
        candidate_places=state.get("candidate_places") or [],
        candidate_restaurants=state.get("candidate_restaurants") or [],
        candidate_hotels=hotels,
        candidate_flights=flights,
        weather=state.get("weather") or [],
        preferences=state.get("preferences") or [],
        trip_pace=trip_pace,
    )

    # Re-validate after optimization swaps.
    errors = validate_itinerary(
        result.itinerary,
        known_place_ids=known_ids_from_candidates(
            state.get("candidate_places") or [],
            state.get("candidate_restaurants") or [],
            hotels,
        )
        + [str(item.get("id")) for item in hotels if item.get("id")],
        require_weather=True,
        weather_available=bool(state.get("weather")),
    )
    # Budget is assessed on the full breakdown (flights+hotels+...); clear stale
    # activity-only budget errors when the optimized total fits.
    if result.budget_breakdown.within_budget:
        errors = [err for err in errors if "exceeds budget" not in err.casefold()]
    elif not any("exceeds budget" in err.casefold() for err in errors):
        errors.append(
            f"Chi phí ước tính {result.budget_breakdown.total} vượt ngân sách "
            f"{result.budget_breakdown.budget} {result.budget_breakdown.currency}."
        )

    notes = [item.text for item in result.explanations]
    notes.extend(result.budget_breakdown.as_notes())

    routes: List[Dict[str, Any]] = []
    for day in result.itinerary.days:
        previous = None
        for activity in day.activities:
            if previous is not None:
                routes.append(
                    {
                        "day_number": day.day_number,
                        "from_place_id": previous.place_id,
                        "to_place_id": activity.place_id,
                        "travel_time_minutes": activity.travel_time_from_previous,
                    }
                )
            previous = activity

    return {
        "itinerary": result.itinerary.model_dump(mode="json"),
        "candidate_hotels": hotels,
        "candidate_flights": flights,
        "budget_breakdown": result.budget_breakdown.model_dump(mode="json"),
        "optimization_notes": notes,
        "validation_errors": errors,
        "routes": routes,
    }


def _airport_hint(value: str) -> str:
    mapping = {
        "hanoi": "HAN",
        "ha noi": "HAN",
        "da nang": "DAD",
        "danang": "DAD",
        "ho chi minh": "SGN",
        "saigon": "SGN",
        "sai gon": "SGN",
    }
    key = value.strip().casefold()
    if len(key) == 3 and key.isalpha():
        return key.upper()
    return mapping.get(key, key[:3].upper())


def finalize_response(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    errors = list(state.get("validation_errors") or [])
    raw = state.get("itinerary")
    if raw is None:
        empty = FinalTravelResponse(
            headline="Không thể dựng kế hoạch chuyến đi",
            overview=state.get("parse_error") or "Trợ lý không tạo được lịch trình.",
            itinerary=TripItinerary(
                destination=state.get("destination") or "Unknown",
                start_date=iso_to_date(state["start_date"])
                if state.get("start_date")
                else ctx.reference_date,
                end_date=iso_to_date(state["end_date"])
                if state.get("end_date")
                else ctx.reference_date,
                travelers=int(state.get("travelers") or 1),
                total_budget=Decimal(state.get("budget") or "0"),
                currency=state.get("currency") or "VND",
            ),
            validation_errors=errors or ["Thiếu lịch trình."],
            is_valid=False,
        )
        return {"final_response": empty.model_dump(mode="json")}

    itinerary = TripItinerary.model_validate(raw)
    weather_notes = [
        (
            f"{item['forecast_date']}: {item['condition']}, "
            f"{item['temperature_min_c']:.0f}–{item['temperature_max_c']:.0f}°C"
        )
        for item in state.get("weather") or []
    ]
    remaining = itinerary.total_budget - itinerary.estimated_total_cost
    budget_notes = [
        f"Chi phí chuyến đi ước tính: {itinerary.estimated_total_cost} {itinerary.currency}",
        f"Ngân sách còn lại: {remaining} {itinerary.currency}",
    ]
    breakdown = state.get("budget_breakdown") or {}
    if breakdown:
        budget_notes.extend(
            [
                (
                    f"Vé máy bay {breakdown.get('flights', 0)}, khách sạn {breakdown.get('hotels', 0)}, "
                    f"ăn uống {breakdown.get('food', 0)}, hoạt động {breakdown.get('activities', 0)}, "
                    f"di chuyển {breakdown.get('transportation', 0)} {itinerary.currency}."
                )
            ]
        )
    knowledge_hits = state.get("knowledge_hits") or []
    knowledge_notes = [
        f"{item.get('title')}: {item.get('excerpt')}"
        for item in knowledge_hits
        if item.get("title") and item.get("excerpt")
    ]
    citations = list(state.get("citations") or [])
    optimization_notes = list(state.get("optimization_notes") or [])
    is_valid = not errors
    headline = (
        f"Chuyến đi {itinerary.destination} cho {itinerary.travelers} người"
        if is_valid
        else f"Bản nháp {itinerary.destination} cần chỉnh sửa"
    )
    overview = itinerary.summary
    if knowledge_notes:
        overview += " Bao gồm kiến thức địa phương có trích dẫn."
    if optimization_notes:
        overview += " Lịch trình đã tối ưu theo ngân sách, khoảng cách, thời tiết và sở thích."
    if errors:
        overview += " Kiểm tra phát hiện vấn đề cần xem lại trước khi đặt chỗ."

    response = FinalTravelResponse(
        headline=headline,
        overview=overview,
        itinerary=itinerary,
        weather_notes=weather_notes,
        budget_notes=budget_notes,
        knowledge_notes=knowledge_notes,
        optimization_notes=optimization_notes,
        citations=citations,
        validation_errors=errors,
        is_valid=is_valid,
    )
    return {"final_response": response.model_dump(mode="json")}


def update_memory(state: TravelAgentState, ctx: TravelAgentContext) -> Dict[str, Any]:
    """Store only explicit/validated preferences extracted from the user request.

    Never invents memories from itineraries, RAG hits, or a single trip destination.
    """
    user_id = state.get("user_id")
    if not user_id:
        return {"memory_updates": []}

    from uuid import UUID

    from app.memory.service import MemoryService

    memory_service = getattr(ctx.dependencies, "memory", None) or MemoryService()

    try:
        uid = UUID(str(user_id))
    except ValueError:
        return {"memory_updates": []}

    updates = memory_service.extract_explicit_updates(
        user_id=uid,
        user_request=state.get("user_request") or "",
    )
    applied: List[Dict[str, Any]] = []
    for update in updates:
        memory_service.update_memory(update)
        applied.append(
            {
                "field": update.field.value,
                "value": update.value,
                "evidence": update.evidence.value,
            }
        )

    return {
        "memory_updates": applied,
        "user_memory": memory_service.get_memory(uid).model_dump(mode="json"),
    }
