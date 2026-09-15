"""Structured logging with secret / PII redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.observability.context import get_request_id

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|access[_-]?token|authorization|password|secret|passwd|credential|bearer)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_KEY_ASSIGN = re.compile(
    r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?([^\s'\",}]+)"
)


def redact_text(value: str) -> str:
    text = _BEARER.sub("Bearer [REDACTED]", value)
    text = _KEY_ASSIGN.sub(r"\1=[REDACTED]", text)
    return text


def redact_mapping(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_KEY.search(str(key)):
            cleaned[key] = "[REDACTED]"
        elif isinstance(value, dict):
            cleaned[key] = redact_mapping(value)
        elif isinstance(value, str):
            cleaned[key] = redact_text(value)
        else:
            cleaned[key] = value
    return cleaned


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_mapping(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True


class RequestIdFormatter(logging.Formatter):
    """Inject request id at format-time to avoid LogRecord extra collisions."""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or "-",
        }
        for key in ("span", "component", "tool", "node", "agent", "provider", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            RequestIdFormatter(
                "%(asctime)s %(levelname)s [%(name)s] [req=%(request_id)s] %(message)s"
            )
        )
    root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
