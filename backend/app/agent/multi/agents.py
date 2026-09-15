"""Specialist agents for the TripMind multi-agent travel graph.

Each agent has one responsibility. They share MultiAgentState and never call
each other directly — only the supervisor dispatches them.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.agent.multi.guards import (
    AGENT_BUDGET,
    AGENT_FLIGHT,
    AGENT_HOTEL,
    AGENT_ITINERARY,
    AGENT_PLACE,
    AGENT_VALIDATION,
    AGENT_WEATHER,
    record_error,
)
from app.agent.nodes import (
    TravelAgentContext,
    _airport_hint,
    finalize_response,
    gather_places,
    gather_restaurants,
    gather_weather,
    generate_itinerary,
    optimize_itinerary,
    update_memory,
    validate_itinerary_node,
)


def _mark_complete(state: Dict[str, Any], agent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    completed = list(state.get("completed_agents") or [])
    if agent not in completed:
        completed.append(agent)
    trace = list(state.get("agent_trace") or [])
    trace.append(agent)
    return {
        **payload,
        "completed_agents": completed,
        "agent_trace": trace,
        "active_agent": None,
    }


def _rank_flights(flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cheaper first, fewer stops as tie-breaker."""
    return sorted(
        flights,
        key=lambda item: (
            float(item.get("price") or 1e18),
            int(item.get("stops") or 0),
        ),
    )


def _rank_hotels(hotels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer higher rating, then lower nightly price."""
    return sorted(
        hotels,
        key=lambda item: (
            -float(item.get("rating") or 0),
            float(item.get("nightly_price") or 1e18),
        ),
    )


def flight_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Search and rank flights when an origin is present.

    Called only when the supervisor includes `flight` in the plan (origin set).
    """
    try:
        if state.get("parse_error") or not state.get("origin") or not state.get("destination"):
            return _mark_complete(state, AGENT_FLIGHT, {"candidate_flights": []})

        existing = list(state.get("candidate_flights") or [])
        if existing:
            return _mark_complete(
                state, AGENT_FLIGHT, {"candidate_flights": _rank_flights(existing)}
            )

        tool = ctx.tools.get("search_flights")
        if tool is None:
            return _mark_complete(state, AGENT_FLIGHT, {"candidate_flights": []})

        result = tool.invoke(
            {
                "origin": _airport_hint(str(state["origin"])),
                "destination": _airport_hint(str(state["destination"])),
                "departure_date": state["start_date"],
                "travelers": int(state.get("travelers") or 1),
                "currency": state.get("currency") or "VND",
            }
        )
        flights = list(result.get("flights") or []) if result.get("success") else []
        return _mark_complete(
            state, AGENT_FLIGHT, {"candidate_flights": _rank_flights(flights)}
        )
    except Exception as exc:  # noqa: BLE001 - recover and continue pipeline
        return _mark_complete(
            state,
            AGENT_FLIGHT,
            {
                "candidate_flights": [],
                "agent_errors": record_error(state, agent=AGENT_FLIGHT, message=str(exc)),
            },
        )


def hotel_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Search and rank hotels for the stay dates."""
    try:
        if (
            state.get("parse_error")
            or not state.get("destination")
            or not state.get("start_date")
            or not state.get("end_date")
        ):
            return _mark_complete(state, AGENT_HOTEL, {"candidate_hotels": []})

        existing = list(state.get("candidate_hotels") or [])
        if existing:
            return _mark_complete(
                state, AGENT_HOTEL, {"candidate_hotels": _rank_hotels(existing)}
            )

        tool = ctx.tools.get("search_hotels")
        if tool is None:
            return _mark_complete(state, AGENT_HOTEL, {"candidate_hotels": []})

        result = tool.invoke(
            {
                "destination": state["destination"],
                "check_in": state["start_date"],
                "check_out": state["end_date"],
                "guests": int(state.get("travelers") or 1),
                "currency": state.get("currency") or "VND",
            }
        )
        hotels = list(result.get("hotels") or []) if result.get("success") else []
        return _mark_complete(
            state, AGENT_HOTEL, {"candidate_hotels": _rank_hotels(hotels)}
        )
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_HOTEL,
            {
                "candidate_hotels": [],
                "agent_errors": record_error(state, agent=AGENT_HOTEL, message=str(exc)),
            },
        )


def place_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Collect attractions and restaurants for the destination."""
    try:
        places = gather_places(state, ctx)  # type: ignore[arg-type]
        merged = {**state, **places}
        restaurants = gather_restaurants(merged, ctx)  # type: ignore[arg-type]
        return _mark_complete(state, AGENT_PLACE, {**places, **restaurants})
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_PLACE,
            {
                "candidate_places": [],
                "candidate_restaurants": [],
                "agent_errors": record_error(state, agent=AGENT_PLACE, message=str(exc)),
            },
        )


def weather_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Fetch per-day weather for the trip window."""
    try:
        weather = gather_weather(state, ctx)  # type: ignore[arg-type]
        return _mark_complete(state, AGENT_WEATHER, weather)
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_WEATHER,
            {
                "weather": [],
                "agent_errors": record_error(state, agent=AGENT_WEATHER, message=str(exc)),
            },
        )


def itinerary_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Build a grounded day-by-day schedule from candidate catalogs."""
    try:
        payload = generate_itinerary(state, ctx)  # type: ignore[arg-type]
        return _mark_complete(state, AGENT_ITINERARY, payload)
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_ITINERARY,
            {
                "itinerary": None,
                "routes": [],
                "agent_errors": record_error(state, agent=AGENT_ITINERARY, message=str(exc)),
            },
        )


def budget_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Cost analysis + itinerary optimization (uses ranked flights/hotels).

    Runs after Itinerary so food/activity/transport lines are real, not guessed.
    Flight/Hotel agents already ranked offers; this agent allocates spend and swaps.
    """
    try:
        payload = optimize_itinerary(state, ctx)  # type: ignore[arg-type]
        # Keep validation_errors for the Validation Agent to own the final verdict.
        # Budget may surface provisional errors; Validation Agent re-checks.
        return _mark_complete(state, AGENT_BUDGET, payload)
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_BUDGET,
            {
                "budget_breakdown": None,
                "optimization_notes": [f"Budget agent fallback: {exc}"],
                "agent_errors": record_error(state, agent=AGENT_BUDGET, message=str(exc)),
            },
        )


def validation_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Detect invalid itineraries (unknown ids, duplicates, budget, weather)."""
    try:
        payload = validate_itinerary_node(state, ctx)  # type: ignore[arg-type]
        # Merge with any budget-stage errors that are still relevant.
        budget_errors = [
            err
            for err in (state.get("validation_errors") or [])
            if "ngân sách" in err.casefold() or "budget" in err.casefold()
        ]
        errors = list(dict.fromkeys([*(payload.get("validation_errors") or []), *budget_errors]))
        # Prefer budget-breakdown awareness when available.
        breakdown = state.get("budget_breakdown") or {}
        if breakdown.get("within_budget"):
            errors = [
                err
                for err in errors
                if "exceeds budget" not in err.casefold() and "vượt ngân sách" not in err.casefold()
            ]
        return _mark_complete(state, AGENT_VALIDATION, {"validation_errors": errors})
    except Exception as exc:  # noqa: BLE001
        return _mark_complete(
            state,
            AGENT_VALIDATION,
            {
                "validation_errors": [f"Validation agent error: {exc}"],
                "agent_errors": record_error(state, agent=AGENT_VALIDATION, message=str(exc)),
            },
        )


def fallback_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Best-effort exit when timeout / max iterations / hard failures hit."""
    notes = list(state.get("optimization_notes") or [])
    notes.append(
        "Đã dùng phương án dự phòng do hết thời gian, vượt số vòng lặp, hoặc lỗi agent."
    )
    errors = list(state.get("validation_errors") or [])
    if not state.get("itinerary") and not errors:
        errors.append("Không hoàn tất lập kế hoạch đầy đủ; trả về kết quả tốt nhất có sẵn.")
    supervisor_notes = list(state.get("supervisor_notes") or [])
    supervisor_notes.append("fallback")
    return {
        "fallback_used": True,
        "optimization_notes": notes,
        "validation_errors": errors,
        "supervisor_notes": supervisor_notes,
        "active_agent": None,
        "agent_trace": list(state.get("agent_trace") or []) + ["fallback"],
    }


def finalize_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    return finalize_response(state, ctx)  # type: ignore[arg-type]


def memory_update_agent(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    return update_memory(state, ctx)  # type: ignore[arg-type]
