"""ASGI middleware: request IDs, rate limits, observability spans."""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.cache import RateLimitExceeded, check_rate_limit
from app.core.config import get_settings
from app.observability import (
    bind_cost_tracker,
    get_cost_tracker,
    new_request_id,
    set_request_id,
    trace_span,
)
from app.observability.context import set_user_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        incoming = request.headers.get("X-Request-ID") or request.headers.get("X-Request-Id")
        request_id = incoming.strip() if incoming else new_request_id()
        set_request_id(request_id)
        set_user_id(None)
        bind_cost_tracker()

        client_host = request.client.host if request.client else "unknown"
        path = request.url.path
        # Health checks skip rate limiting.
        if settings.rate_limit_enabled and not path.endswith("/health"):
            try:
                limit = settings.rate_limit_requests
                window = settings.rate_limit_window_seconds
                if path.rstrip("/").endswith("/trips/plan"):
                    limit = settings.rate_limit_plan_requests
                    window = settings.rate_limit_plan_window_seconds
                check_rate_limit(
                    f"{client_host}:{path}",
                    limit=limit,
                    window_seconds=window,
                    settings=settings,
                )
            except RateLimitExceeded as exc:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Quá nhiều yêu cầu. Vui lòng thử lại sau.",
                        "code": "rate_limited",
                        "request_id": request_id,
                    },
                    headers={
                        "Retry-After": str(exc.retry_after),
                        "X-Request-ID": request_id,
                    },
                )

        started = time.monotonic()
        with trace_span("request", f"{request.method} {path}", method=request.method, path=path):
            response = await call_next(request)
        duration_ms = int((time.monotonic() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        tracker = get_cost_tracker()
        if tracker and tracker.total_estimated_usd > 0:
            response.headers["X-Cost-USD"] = f"{tracker.total_estimated_usd:.6f}"
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
