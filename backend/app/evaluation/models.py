"""Typed models for TripMind agent evaluation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """One gold-labeled travel request."""

    id: str
    user_request: str
    expected_destination: str
    expected_origin: Optional[str] = None
    expected_days: int
    expected_travelers: int
    expected_budget_total: Decimal
    expected_budget_per_person: Optional[Decimal] = None
    expected_preferences: List[str] = Field(default_factory=list)
    expected_currency: str = "VND"
    reference_date: date = date(2026, 10, 12)
    # Tools the agent must use for a correct grounded plan.
    required_tools: List[str] = Field(default_factory=list)
    # Tools that must NOT be used for this case.
    forbidden_tools: List[str] = Field(default_factory=list)


class CaseScores(BaseModel):
    case_id: str
    destination: float
    dates: float
    budget: float
    travelers: float
    preferences: float
    request_understanding: float
    tool_selection: float
    itinerary_validity: float
    budget_validity: float
    duplicate_free: float
    unsupported_claims_rate: float
    hallucination_rate: float
    details: Dict[str, Any] = Field(default_factory=dict)


class AggregateMetrics(BaseModel):
    request_understanding: float
    tool_selection: float
    budget_validity: float
    itinerary_validity: float
    duplicate_free: float
    unsupported_claims: float
    hallucination_rate: float
    case_count: int


class EvaluationReport(BaseModel):
    created_at: str
    reference_date: str
    metrics: AggregateMetrics
    cases: List[CaseScores]
    summary_lines: List[str] = Field(default_factory=list)

    def format_summary(self) -> str:
        m = self.metrics
        return "\n".join(
            [
                "Agent Evaluation",
                "",
                f"Request understanding: {_pct(m.request_understanding)}",
                f"Tool selection: {_pct(m.tool_selection)}",
                f"Budget validity: {_pct(m.budget_validity)}",
                f"Itinerary validity: {_pct(m.itinerary_validity)}",
                f"Duplicate-free days: {_pct(m.duplicate_free)}",
                f"Unsupported claims: {_pct(m.unsupported_claims)}",
                f"Hallucination rate: {_pct(m.hallucination_rate)}",
            ]
        )


def _pct(value: float) -> str:
    return f"{round(value * 100)}%"
