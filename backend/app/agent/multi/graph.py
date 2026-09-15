"""Compile the controlled multi-agent TripMind travel graph."""

from __future__ import annotations

from datetime import date
from functools import partial
from typing import Any, Dict, Optional

from langgraph.graph import END, START, StateGraph

from app.agent.multi.agents import (
    budget_agent,
    fallback_agent,
    finalize_agent,
    flight_agent,
    hotel_agent,
    itinerary_agent,
    memory_update_agent,
    place_agent,
    validation_agent,
    weather_agent,
)
from app.agent.multi.state import MultiAgentState
from app.agent.multi.supervisor import bootstrap, route_from_supervisor, supervisor
from app.agent.nodes import TravelAgentContext
from app.agent.parser import RequestParser
from app.tools import ToolDependencies


def build_multi_agent_graph(
    *,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
    tools: Optional[Dict[str, Any]] = None,
):
    """
    Controlled multi-agent architecture::

                    Supervisor
                        │
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
    Flight           Hotel            Place
       │                │                │
       └────────────────┼────────────────┘
                        ↓
                   Weather Agent
                        ↓
                 Itinerary Agent
                        ↓
                   Budget Agent
                        ↓
                Validation Agent
                        ↓
                    Finalize

    Supervisor understands the request, plans which agents are required
    (Flight only when origin is present), and dispatches from a shared queue.
    Loop guards: max iterations, timeout, error recovery, fallback finalize.
    """
    ctx = TravelAgentContext(
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
        tools=tools,
    )

    graph = StateGraph(MultiAgentState)
    graph.add_node("bootstrap", partial(bootstrap, ctx=ctx))
    graph.add_node("supervisor", partial(supervisor, ctx=ctx))
    graph.add_node("flight", partial(flight_agent, ctx=ctx))
    graph.add_node("hotel", partial(hotel_agent, ctx=ctx))
    graph.add_node("place", partial(place_agent, ctx=ctx))
    graph.add_node("weather", partial(weather_agent, ctx=ctx))
    graph.add_node("itinerary", partial(itinerary_agent, ctx=ctx))
    graph.add_node("budget", partial(budget_agent, ctx=ctx))
    graph.add_node("validation", partial(validation_agent, ctx=ctx))
    graph.add_node("fallback", partial(fallback_agent, ctx=ctx))
    graph.add_node("finalize", partial(finalize_agent, ctx=ctx))
    graph.add_node("update_memory", partial(memory_update_agent, ctx=ctx))

    graph.add_edge(START, "bootstrap")
    graph.add_edge("bootstrap", "supervisor")

    specialist_targets = {
        "flight": "flight",
        "hotel": "hotel",
        "place": "place",
        "weather": "weather",
        "itinerary": "itinerary",
        "budget": "budget",
        "validation": "validation",
        "finalize": "finalize",
        "fallback": "fallback",
    }
    graph.add_conditional_edges("supervisor", route_from_supervisor, specialist_targets)

    for agent in (
        "flight",
        "hotel",
        "place",
        "weather",
        "itinerary",
        "budget",
        "validation",
    ):
        graph.add_edge(agent, "supervisor")

    graph.add_edge("fallback", "finalize")
    graph.add_edge("finalize", "update_memory")
    graph.add_edge("update_memory", END)
    return graph.compile()


def run_multi_agent(
    user_request: str,
    *,
    user_id: Optional[str] = None,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    app = build_multi_agent_graph(
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
    )
    initial: Dict[str, Any] = {"user_request": user_request}
    if user_id:
        initial["user_id"] = user_id
    return app.invoke(initial)
