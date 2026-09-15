"""Explicit LangGraph state for the TripMind travel agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class TravelAgentState(TypedDict, total=False):
    user_request: str
    user_id: Optional[str]
    destination: Optional[str]
    origin: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    travelers: Optional[int]
    budget: Optional[str]
    currency: Optional[str]
    preferences: List[str]
    user_memory: Optional[Dict[str, Any]]
    memory_updates: List[Dict[str, Any]]
    candidate_places: List[Dict[str, Any]]
    candidate_restaurants: List[Dict[str, Any]]
    candidate_hotels: List[Dict[str, Any]]
    candidate_flights: List[Dict[str, Any]]
    weather: List[Dict[str, Any]]
    routes: List[Dict[str, Any]]
    knowledge_hits: List[Dict[str, Any]]
    citations: List[str]
    itinerary: Optional[Dict[str, Any]]
    budget_breakdown: Optional[Dict[str, Any]]
    optimization_notes: List[str]
    validation_errors: List[str]
    final_response: Optional[Dict[str, Any]]
    parse_error: Optional[str]
    # Multi-agent control plane (shared with MultiAgentState)
    agent_queue: List[str]
    completed_agents: List[str]
    agent_trace: List[str]
    agent_errors: List[Dict[str, Any]]
    supervisor_notes: List[str]
    active_agent: Optional[str]
    iteration: int
    max_iterations: int
    deadline_ts: float
    fallback_used: bool
    repair_attempts: int
