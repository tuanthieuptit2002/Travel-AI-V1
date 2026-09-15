"""Tool call limiting and tracing wrappers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.observability.tracing import trace_tool


class ToolCallLimitExceeded(RuntimeError):
    """Raised when an agent exceeds the configured max tool-call budget."""


class LimitedToolProxy:
    """Proxy that enforces max tool calls and emits observability events."""

    def __init__(
        self,
        inner: Any,
        *,
        counter: Dict[str, int],
        max_calls: int,
        tool_name: str,
    ) -> None:
        self._inner = inner
        self._counter = counter
        self._max_calls = max_calls
        self.name = getattr(inner, "name", tool_name)
        self.description = getattr(inner, "description", tool_name)

    def invoke(self, input: Any = None, config: Any = None, **kwargs: Any) -> Any:
        used = int(self._counter.get("count", 0))
        if used >= self._max_calls:
            raise ToolCallLimitExceeded(
                f"Tool call limit reached ({self._max_calls})."
            )
        self._counter["count"] = used + 1
        trace_tool(self.name)
        if kwargs and input is None:
            return (
                self._inner.invoke(kwargs, config=config)
                if config is not None
                else self._inner.invoke(kwargs)
            )
        if config is not None:
            return self._inner.invoke(input, config=config)
        return self._inner.invoke(input)


def wrap_tools_with_limits(
    tools: Dict[str, Any],
    *,
    max_calls: Optional[int] = None,
    counter: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    limit = max_calls if max_calls is not None else get_settings().agent_max_tool_calls
    shared = counter if counter is not None else {"count": 0}
    return {
        name: LimitedToolProxy(tool, counter=shared, max_calls=limit, tool_name=name)
        for name, tool in tools.items()
    }
