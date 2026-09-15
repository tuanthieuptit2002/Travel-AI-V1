"""Optional Sentry / error-tracking bootstrap."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import Settings

logger = logging.getLogger(__name__)
_sentry_ready = False


def init_error_tracking(settings: Settings) -> None:
    global _sentry_ready
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            before_send=_scrub_event,
        )
        _sentry_ready = True
        logger.info("Sentry error tracking enabled")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize Sentry: %s", type(exc).__name__)


def capture_exception(exc: BaseException, *, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _sentry_ready:
        logger.exception("Unhandled error", exc_info=exc)
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if extra:
                for key, value in extra.items():
                    if key.lower() in {"password", "token", "api_key", "authorization"}:
                        continue
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to report exception to Sentry")


def _scrub_event(event: Dict[str, Any], _hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Drop obvious secrets from breadcrumbs / request headers.
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for key in list(headers):
        if key.lower() in {"authorization", "x-api-key", "cookie"}:
            headers[key] = "[REDACTED]"
    return event
