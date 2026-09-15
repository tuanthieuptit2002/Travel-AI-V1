from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.cache import redis_ping
from app.core.config import get_settings
from app.db.session import database_ping

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    database: str
    redis: str
    auth_enabled: bool
    travel_data_mode: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe; it intentionally has no infrastructure dependency."""
    return HealthResponse(status="ok", service="api")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe for DB/Redis. Degraded components are reported explicitly."""
    settings = get_settings()
    db_ok = database_ping()
    redis_ok = redis_ping(settings)
    # In development, Redis/DB may be optional; still report status.
    overall = "ok" if db_ok else "degraded"
    if settings.is_production and (not db_ok or not redis_ok):
        overall = "not_ready"
    return ReadinessResponse(
        status=overall,
        service="api",
        database="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        auth_enabled=settings.auth_enabled,
        travel_data_mode=settings.travel_data_mode,
    )
