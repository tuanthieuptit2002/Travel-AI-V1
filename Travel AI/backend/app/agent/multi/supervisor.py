"""Supervisor: understand request, decide agents, coordinate execution."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from app.agent.multi.guards import (
    AGENT_BUDGET,
    AGENT_ITINERARY,
    AGENT_VALIDATION,
    advance_queue,
    bump_iteration,
    initial_guard_fields,
    iterations_exceeded,
    max_repair_attempts,
    next_agent,
    plan_required_agents,
    timed_out,
)
from app.agent.nodes import (
    TravelAgentContext,
    gather_knowledge,
    parse_request,
    retrieve_memory,
)

RouteTarget = Literal[
    "flight",
    "hotel",
    "place",
    "weather",
    "itinerary",
    "budget",
    "validation",
    "finalize",
    "fallback",
]


def bootstrap(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Parse request, load memory + RAG, initialize guards, plan agent queue.

    Memory and knowledge stay on the supervisor path — they are cross-cutting
    context, not domain specialists like Flight or Hotel.
    """
    updates: Dict[str, Any] = {}
    updates.update(parse_request(state, ctx))  # type: ignore[arg-type]
    merged = {**state, **updates}
    updates.update(retrieve_memory(merged, ctx))  # type: ignore[arg-type]
    merged = {**merged, **updates}
    updates.update(gather_knowledge(merged, ctx))  # type: ignore[arg-type]
    merged = {**merged, **updates}

    guards = initial_guard_fields()
    notes: List[str] = list(guards["supervisor_notes"])

    if merged.get("parse_error"):
        queue: List[str] = []
        notes.append("Parse failed — skipping specialist agents and finalizing.")
    else:
        has_origin = bool(merged.get("origin"))
        queue = plan_required_agents(
            has_origin=has_origin,
            needs_flights=has_origin,
            needs_hotels=True,
        )
        notes.append(
            "Supervisor plan: "
            + (", ".join(queue) if queue else "(none)")
            + (
                " (flight included because origin is set)"
                if has_origin
                else " (flight skipped — no origin)"
            )
        )

    return {
        **updates,
        **guards,
        "agent_queue": queue,
        "supervisor_notes": notes,
        "agent_trace": ["bootstrap"],
    }


def supervisor(state: Dict[str, Any], ctx: TravelAgentContext) -> Dict[str, Any]:
    """Decide the next specialist (or finalize / fallback).

    Loop guards:
    - max iterations
    - monotonic deadline (timeout)
    - at most one repair re-queue for a missing itinerary
    """
    del ctx  # supervisor is pure control-plane; tools already ran in bootstrap/agents
    iteration_update = bump_iteration(state)
    merged = {**state, **iteration_update}
    notes = list(state.get("supervisor_notes") or [])

    if timed_out(merged):
        notes.append("Timeout — routing to fallback.")
        return {
            **iteration_update,
            "supervisor_notes": notes,
            "fallback_used": True,
            "active_agent": "fallback",
            "agent_queue": [],
        }

    if iterations_exceeded(merged):
        notes.append("Max iterations — routing to fallback.")
        return {
            **iteration_update,
            "supervisor_notes": notes,
            "fallback_used": True,
            "active_agent": "fallback",
            "agent_queue": [],
        }

    queue = list(state.get("agent_queue") or [])

    # One repair attempt if itinerary agent finished but produced nothing.
    repair = int(state.get("repair_attempts") or 0)
    completed = set(state.get("completed_agents") or [])
    if (
        not queue
        and repair < max_repair_attempts()
        and not state.get("parse_error")
        and not state.get("itinerary")
        and AGENT_ITINERARY in completed
        and not state.get("fallback_used")
    ):
        notes.append(
            "Repair: itinerary missing after first pass — re-queue itinerary→budget→validation."
        )
        queue = [AGENT_ITINERARY, AGENT_BUDGET, AGENT_VALIDATION]
        return {
            **iteration_update,
            "repair_attempts": repair + 1,
            "agent_queue": advance_queue(queue),
            "active_agent": next_agent(queue),
            "supervisor_notes": notes,
            "agent_trace": list(state.get("agent_trace") or [])
            + [f"supervisor→{next_agent(queue)}"],
        }

    if not queue:
        notes.append("Queue empty — finalizing.")
        return {
            **iteration_update,
            "active_agent": "finalize",
            "supervisor_notes": notes,
            "agent_trace": list(state.get("agent_trace") or []) + ["supervisor→finalize"],
        }

    agent = next_agent(queue)
    remaining = advance_queue(queue)
    notes.append(f"Dispatch {agent}.")
    return {
        **iteration_update,
        "agent_queue": remaining,
        "active_agent": agent,
        "supervisor_notes": notes,
        "agent_trace": list(state.get("agent_trace") or []) + [f"supervisor→{agent}"],
    }


def route_from_supervisor(state: Dict[str, Any]) -> RouteTarget:
    active = state.get("active_agent") or "finalize"
    if active == "fallback":
        return "fallback"
    if active == "finalize":
        return "finalize"
    if active in {
        "flight",
        "hotel",
        "place",
        "weather",
        "itinerary",
        "budget",
        "validation",
    }:
        return active  # type: ignore[return-value]
    return "finalize"
