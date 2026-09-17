"""Request-scoped observability context and cost tracking."""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_cost_tracker: ContextVar[Optional["CostTracker"]] = ContextVar("cost_tracker", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(value: Optional[str]) -> None:
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def set_user_id(value: Optional[str]) -> None:
    _user_id.set(value)


def get_user_id() -> Optional[str]:
    return _user_id.get()


@dataclass
class CostEvent:
    component: str  # llm | embedding | provider | agent
    model_or_provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostTracker:
    events: List[CostEvent] = field(default_factory=list)
    tool_calls: int = 0
    provider_calls: int = 0
    llm_calls: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def add(self, event: CostEvent) -> None:
        self.events.append(event)
        if event.component in {"llm", "embedding"}:
            self.llm_calls += 1

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def record_provider_call(self) -> None:
        self.provider_calls += 1

    @property
    def total_estimated_usd(self) -> float:
        return sum(event.estimated_usd for event in self.events)

    @property
    def total_tokens(self) -> int:
        return sum(event.input_tokens + event.output_tokens for event in self.events)

    def summary(self) -> Dict[str, Any]:
        return {
            "tool_calls": self.tool_calls,
            "provider_calls": self.provider_calls,
            "llm_calls": self.llm_calls,
            "total_tokens": self.total_tokens,
            "estimated_usd": round(self.total_estimated_usd, 6),
            "duration_ms": int((time.monotonic() - self.started_at) * 1000),
            "events": [
                {
                    "component": e.component,
                    "model_or_provider": e.model_or_provider,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "estimated_usd": e.estimated_usd,
                }
                for e in self.events
            ],
        }


def bind_cost_tracker(tracker: Optional[CostTracker] = None) -> CostTracker:
    active = tracker or CostTracker()
    _cost_tracker.set(active)
    return active


def get_cost_tracker() -> Optional[CostTracker]:
    return _cost_tracker.get()


def estimate_embedding_cost(*, tokens: int, per_1k: float) -> float:
    return (tokens / 1000.0) * per_1k


def estimate_chat_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_per_1k: float,
    output_per_1k: float,
) -> float:
    return (input_tokens / 1000.0) * input_per_1k + (output_tokens / 1000.0) * output_per_1k
