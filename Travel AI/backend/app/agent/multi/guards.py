"""Loop / timeout / fallback guards for the multi-agent supervisor."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

# Hard caps — prevent infinite supervisor ↔ agent loops.
DEFAULT_MAX_ITERATIONS = 16
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_REPAIR_ATTEMPTS = 1


def max_repair_attempts() -> int:
    try:
        return int(get_settings().agent_max_repair_attempts)
    except Exception:  # noqa: BLE001
        return DEFAULT_MAX_REPAIR_ATTEMPTS

AGENT_FLIGHT = "flight"
AGENT_HOTEL = "hotel"
AGENT_PLACE = "place"
AGENT_WEATHER = "weather"
AGENT_BUDGET = "budget"
AGENT_ITINERARY = "itinerary"
AGENT_VALIDATION = "validation"

# Canonical execution order after supervisor planning.
# Budget runs after Itinerary because full cost analysis needs a schedule;
# Flight/Hotel agents already rank offers beforehand.
CANONICAL_ORDER = [
    AGENT_FLIGHT,
    AGENT_HOTEL,
    AGENT_PLACE,
    AGENT_WEATHER,
    AGENT_ITINERARY,
    AGENT_BUDGET,
    AGENT_VALIDATION,
]


def now_ts() -> float:
    return time.monotonic()


def initial_guard_fields(
    *,
    max_iterations: Optional[int] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        from app.core.config import get_settings

        settings = get_settings()
        max_iterations = max_iterations if max_iterations is not None else settings.agent_max_iterations
        timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.agent_timeout_seconds
        )
    except Exception:  # noqa: BLE001
        max_iterations = max_iterations if max_iterations is not None else DEFAULT_MAX_ITERATIONS
        timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS
        )
    return {
        "agent_queue": [],
        "completed_agents": [],
        "agent_trace": [],
        "agent_errors": [],
        "supervisor_notes": [],
        "active_agent": None,
        "iteration": 0,
        "max_iterations": int(max_iterations),
        "deadline_ts": now_ts() + float(timeout_seconds),
        "fallback_used": False,
        "repair_attempts": 0,
    }


def timed_out(state: Dict[str, Any]) -> bool:
    deadline = float(state.get("deadline_ts") or 0)
    return deadline > 0 and now_ts() > deadline


def iterations_exceeded(state: Dict[str, Any]) -> bool:
    iteration = int(state.get("iteration") or 0)
    maximum = int(state.get("max_iterations") or DEFAULT_MAX_ITERATIONS)
    return iteration >= maximum


def should_stop(state: Dict[str, Any]) -> bool:
    return bool(state.get("fallback_used")) or timed_out(state) or iterations_exceeded(state)


def bump_iteration(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"iteration": int(state.get("iteration") or 0) + 1}


def record_error(
    state: Dict[str, Any],
    *,
    agent: str,
    message: str,
) -> List[Dict[str, Any]]:
    errors = list(state.get("agent_errors") or [])
    errors.append({"agent": agent, "message": message, "at": now_ts()})
    return errors


def plan_required_agents(
    *,
    has_origin: bool,
    needs_flights: bool,
    needs_hotels: bool = True,
) -> List[str]:
    """Decide which specialist agents are required for this request.

    Agents are only included when they have a clear job — never padded.
    """
    queue: List[str] = []
    if needs_flights and has_origin:
        queue.append(AGENT_FLIGHT)
    if needs_hotels:
        queue.append(AGENT_HOTEL)
    queue.extend(
        [
            AGENT_PLACE,
            AGENT_WEATHER,
            AGENT_ITINERARY,
            AGENT_BUDGET,
            AGENT_VALIDATION,
        ]
    )
    return queue


def next_agent(queue: Optional[List[str]]) -> Optional[str]:
    if not queue:
        return None
    return queue[0]


def advance_queue(queue: Optional[List[str]]) -> List[str]:
    if not queue:
        return []
    return list(queue[1:])
