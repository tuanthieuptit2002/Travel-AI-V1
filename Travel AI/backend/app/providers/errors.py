"""Structured provider errors that never include secrets or raw upstream payloads."""

from __future__ import annotations

from typing import Optional


class ProviderError(Exception):
    """Safe, structured failure from an external travel-data provider."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        code: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.code = code
        self.status_code = status_code

    def __str__(self) -> str:
        return f"{self.provider}:{self.code}: {self.message}"
