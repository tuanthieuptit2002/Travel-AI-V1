"""Previous single-pipeline LangGraph travel agent (kept for comparison)."""

from __future__ import annotations

from datetime import date
from functools import partial
from typing import Any, Dict, Optional

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    TravelAgentContext,
    finalize_response,
    gather_knowledge,
    gather_places,
    gather_restaurants,
    gather_weather,
    generate_itinerary,
    optimize_itinerary,
    parse_request,
    retrieve_memory,
    update_memory,
    validate_itinerary_node,
)
from app.agent.parser import RequestParser
from app.agent.state import TravelAgentState
from app.tools import ToolDependencies


def build_legacy_travel_agent_graph(
    *,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
    tools: Optional[Dict[str, Any]] = None,
):
    """
    Linear single-agent pipeline (pre multi-agent refactor)::

        parse → memory → places → restaurants → weather → knowledge
             → itinerary → validate → optimize → finalize → memory
    """
    ctx = TravelAgentContext(
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
        tools=tools,
    )

    graph = StateGraph(TravelAgentState)
    graph.add_node("parse_request", partial(parse_request, ctx=ctx))
    graph.add_node("retrieve_memory", partial(retrieve_memory, ctx=ctx))
    graph.add_node("gather_places", partial(gather_places, ctx=ctx))
    graph.add_node("gather_restaurants", partial(gather_restaurants, ctx=ctx))
    graph.add_node("gather_weather", partial(gather_weather, ctx=ctx))
    graph.add_node("gather_knowledge", partial(gather_knowledge, ctx=ctx))
    graph.add_node("generate_itinerary", partial(generate_itinerary, ctx=ctx))
    graph.add_node("validate_itinerary", partial(validate_itinerary_node, ctx=ctx))
    graph.add_node("optimize_itinerary", partial(optimize_itinerary, ctx=ctx))
    graph.add_node("finalize_response", partial(finalize_response, ctx=ctx))
    graph.add_node("update_memory", partial(update_memory, ctx=ctx))

    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "retrieve_memory")
    graph.add_edge("retrieve_memory", "gather_places")
    graph.add_edge("gather_places", "gather_restaurants")
    graph.add_edge("gather_restaurants", "gather_weather")
    graph.add_edge("gather_weather", "gather_knowledge")
    graph.add_edge("gather_knowledge", "generate_itinerary")
    graph.add_edge("generate_itinerary", "validate_itinerary")
    graph.add_edge("validate_itinerary", "optimize_itinerary")
    graph.add_edge("optimize_itinerary", "finalize_response")
    graph.add_edge("finalize_response", "update_memory")
    graph.add_edge("update_memory", END)
    return graph.compile()


def run_legacy_travel_agent(
    user_request: str,
    *,
    user_id: Optional[str] = None,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    app = build_legacy_travel_agent_graph(
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
    )
    initial: Dict[str, Any] = {"user_request": user_request}
    if user_id:
        initial["user_id"] = user_id
    return app.invoke(initial)
