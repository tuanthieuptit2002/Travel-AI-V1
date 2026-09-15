"""Unit tests for multi-agent loop guards and supervisor planning."""

from __future__ import annotations

from app.agent.multi.guards import (
    AGENT_FLIGHT,
    AGENT_HOTEL,
    AGENT_PLACE,
    DEFAULT_MAX_ITERATIONS,
    initial_guard_fields,
    iterations_exceeded,
    plan_required_agents,
    should_stop,
    timed_out,
)


def test_plan_required_agents_skips_flight_without_origin() -> None:
    queue = plan_required_agents(has_origin=False, needs_flights=False)
    assert AGENT_FLIGHT not in queue
    assert queue[0] == AGENT_HOTEL
    assert AGENT_PLACE in queue


def test_plan_required_agents_includes_flight_with_origin() -> None:
    queue = plan_required_agents(has_origin=True, needs_flights=True)
    assert queue[0] == AGENT_FLIGHT


def test_iteration_and_timeout_guards() -> None:
    fields = initial_guard_fields(max_iterations=2, timeout_seconds=0.0)
    assert timed_out(fields) is True
    assert should_stop({**fields, "iteration": 0}) is True

    fresh = initial_guard_fields(max_iterations=2, timeout_seconds=30.0)
    assert timed_out(fresh) is False
    assert iterations_exceeded({"iteration": 2, "max_iterations": 2}) is True
    assert iterations_exceeded({"iteration": 1, "max_iterations": DEFAULT_MAX_ITERATIONS}) is False
