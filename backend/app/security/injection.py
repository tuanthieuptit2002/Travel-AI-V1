"""Prompt-injection and unsafe URL defenses."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional
from urllib.parse import urlparse

# Patterns commonly used to hijack agent instructions or tool selection.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"system\s+prompt",
        r"you\s+are\s+now\s+",
        r"jailbreak",
        r"do\s+not\s+follow\s+your\s+rules",
        r"reveal\s+(your\s+)?(system|hidden)\s+prompt",
        r"<\s*/?\s*system\s*>",
        r"```\s*system",
        r"tool_call\s*\(",
        r"execute\s+shell",
        r"run\s+bash",
        r"DROP\s+TABLE",
        r"UNION\s+SELECT",
        r";\s*SHUTDOWN",
    )
]

_ALLOWED_URL_SCHEMES = {"https"}
_BLOCKED_HOST_SUFFIXES = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
)


def sanitize_user_request(text: str, *, max_length: int = 4000) -> str:
    """Normalize user text and neutralize common prompt-injection phrases."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[filtered]", cleaned)
    return cleaned


def detect_injection(text: str) -> List[str]:
    hits: List[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text or ""):
            hits.append(pattern.pattern)
    return hits


def is_safe_external_url(url: str, *, allowed_hosts: Optional[Iterable[str]] = None) -> bool:
    """Never trust LLM-generated URLs blindly — allowlist scheme/host."""
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        return False
    host = (parsed.hostname or "").casefold()
    if not host:
        return False
    if any(host == blocked or host.endswith("." + blocked) for blocked in _BLOCKED_HOST_SUFFIXES):
        return False
    if host.replace(".", "").isdigit():
        # Block raw IPs by default (SSRF mitigation).
        return False
    if allowed_hosts:
        allow = {item.casefold() for item in allowed_hosts}
        if host not in allow and not any(host.endswith("." + item) for item in allow):
            return False
    return True
