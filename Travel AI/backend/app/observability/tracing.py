"""Trace helpers for request → agent → node → tool → provider → LLM → response."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from app.observability.context import get_cost_tracker

logger = logging.getLogger("tripmind.trace")


def _emit(span: str, message: str, **fields: Any) -> None:
    # Keep extras on a nested dict so they never collide with LogRecord builtins
    # (e.g. request_id, filename, module, pathname, ...).
    safe_fields = {k: v for k, v in fields.items() if k.isidentifier()}
    logger.info("%s | span=%s | %s", message, span, safe_fields)


@contextmanager
def trace_span(span: str, message: str, **fields: Any) -> Iterator[Dict[str, Any]]:
    started = time.monotonic()
    payload = dict(fields)
    _emit(span, f"start {message}", **payload)
    try:
        yield payload
    except Exception:
        duration_ms = int((time.monotonic() - started) * 1000)
        _emit(span, f"error {message}", duration_ms=duration_ms, **payload)
        raise
    else:
        duration_ms = int((time.monotonic() - started) * 1000)
        _emit(span, f"end {message}", duration_ms=duration_ms, **payload)


def trace_tool(tool_name: str) -> None:
    tracker = get_cost_tracker()
    if tracker:
        tracker.record_tool_call()
    _emit("tool", f"tool_call name={tool_name}", tool=tool_name, component="tool")


def trace_provider(provider: str, method: str, url: str) -> None:
    tracker = get_cost_tracker()
    if tracker:
        tracker.record_provider_call()
    _emit(
        "external_api",
        f"provider_call provider={provider} method={method}",
        provider=provider,
        component="provider",
        http_method=method,
        url=url,
    )


def trace_llm(model: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
    _emit(
        "llm",
        f"llm_call model={model} in={input_tokens} out={output_tokens}",
        component="llm",
        llm_model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def trace_agent_node(node: str, agent: Optional[str] = None) -> None:
    _emit("node", f"agent_node={node}", node=node, agent=agent, component="agent")
