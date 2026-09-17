"""Instrument agent tools to record which tools were invoked."""

from __future__ import annotations

from typing import Any, Dict, List, Set


class ToolCallRecorder:
    """Wrap tool dicts and record every invoke by tool name."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    @property
    def unique_calls(self) -> Set[str]:
        return set(self.calls)

    def wrap(self, tools: Dict[str, Any]) -> Dict[str, Any]:
        return {name: _RecordingProxy(tool, self, name) for name, tool in tools.items()}


class _RecordingProxy:
    def __init__(self, inner: Any, recorder: ToolCallRecorder, tool_name: str) -> None:
        self._inner = inner
        self._recorder = recorder
        self.name = getattr(inner, "name", tool_name)
        self.description = getattr(inner, "description", tool_name)

    def invoke(self, input: Any = None, config: Any = None, **kwargs: Any) -> Any:
        if kwargs and input is None:
            result = self._inner.invoke(kwargs, config=config) if config is not None else self._inner.invoke(kwargs)
        elif config is not None:
            result = self._inner.invoke(input, config=config)
        else:
            result = self._inner.invoke(input)
        self._recorder.calls.append(self.name)
        return result
