"""Compile the TripMind LangGraph travel agent (multi-agent supervisor)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.agent.multi.graph import build_multi_agent_graph, run_multi_agent
from app.agent.parser import RequestParser
from app.tools import ToolDependencies

# Re-export legacy linear pipeline for comparison / tests.
from app.agent.legacy_graph import (  # noqa: F401
    build_legacy_travel_agent_graph,
    run_legacy_travel_agent,
)


def build_travel_agent_graph(
    *,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
    tools: Optional[Dict[str, Any]] = None,
):
    """Build the controlled multi-agent supervisor graph (current default)."""
    return build_multi_agent_graph(
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
        tools=tools,
    )


def run_travel_agent(
    user_request: str,
    *,
    user_id: Optional[str] = None,
    dependencies: Optional[ToolDependencies] = None,
    parser: Optional[RequestParser] = None,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Execute the multi-agent graph and return the final shared state."""
    return run_multi_agent(
        user_request,
        user_id=user_id,
        dependencies=dependencies,
        parser=parser,
        reference_date=reference_date,
    )
