"""Shared HTTP helpers for provider adapters (timeouts, retries, rate limits)."""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping, MutableMapping, Optional

import httpx

from app.observability.tracing import trace_provider
from app.providers.errors import ProviderError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class ProviderHttpClient:
    """Thin httpx wrapper with timeout, retry, and secret-safe logging."""

    def __init__(
        self,
        *,
        provider: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = backoff_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ProviderHttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        trace_provider(self.provider, method, _safe_url(url))
        attempt = 0
        last_error: Optional[Exception] = None
        while attempt <= self.max_retries:
            try:
                response = self._client.request(
                    method,
                    url,
                    headers=dict(headers or {}),
                    params=dict(params or {}),
                    json=json_body,
                    timeout=self.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("%s request timed out method=%s url=%s attempt=%s", self.provider, method, _safe_url(url), attempt)
                if attempt >= self.max_retries:
                    raise ProviderError(
                        "Upstream request timed out.",
                        provider=self.provider,
                        code="timeout",
                    ) from exc
                self._sleep(attempt, retry_after=None)
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("%s transport error method=%s url=%s attempt=%s", self.provider, method, _safe_url(url), attempt)
                if attempt >= self.max_retries:
                    raise ProviderError(
                        "Upstream transport error.",
                        provider=self.provider,
                        code="transport_error",
                    ) from exc
                self._sleep(attempt, retry_after=None)
                attempt += 1
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                retry_after = _parse_retry_after(response.headers)
                logger.warning(
                    "%s retryable status=%s method=%s url=%s attempt=%s",
                    self.provider,
                    response.status_code,
                    method,
                    _safe_url(url),
                    attempt,
                )
                self._sleep(attempt, retry_after=retry_after)
                attempt += 1
                continue

            if response.status_code == 429:
                raise ProviderError(
                    "Upstream rate limit exceeded.",
                    provider=self.provider,
                    code="rate_limited",
                    status_code=429,
                )
            if response.status_code >= 400:
                logger.error(
                    "%s upstream error status=%s method=%s url=%s",
                    self.provider,
                    response.status_code,
                    method,
                    _safe_url(url),
                )
                raise ProviderError(
                    "Upstream provider returned an error.",
                    provider=self.provider,
                    code="upstream_error",
                    status_code=response.status_code,
                )
            return response

        raise ProviderError(
            "Upstream request failed after retries.",
            provider=self.provider,
            code="retry_exhausted",
        ) from last_error

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs).json()

    def post_json(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs).json()

    def _sleep(self, attempt: int, *, retry_after: Optional[float]) -> None:
        delay = retry_after if retry_after is not None else self.backoff_seconds * (2**attempt)
        time.sleep(min(delay, 8.0))


def _safe_url(url: str) -> str:
    """Strip query strings so API keys in query params are never logged."""
    return url.split("?", 1)[0]


def _parse_retry_after(headers: MutableMapping[str, str] | httpx.Headers) -> Optional[float]:
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
