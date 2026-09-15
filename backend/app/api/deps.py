"""FastAPI dependencies for trip planning routes."""

from __future__ import annotations

from functools import lru_cache

from app.memory.service import MemoryService
from app.memory.store import get_memory_store
from app.providers.factory import build_tool_dependencies
from app.services.planning_service import PlanningService
from app.services.trip_store import get_trip_store


@lru_cache
def get_planning_service() -> PlanningService:
    return PlanningService(
        store=get_trip_store(),
        dependencies=build_tool_dependencies(),
    )


def reset_planning_service_cache() -> None:
    get_planning_service.cache_clear()


@lru_cache
def get_memory_service() -> MemoryService:
    return MemoryService(store=get_memory_store())


def reset_memory_service_cache() -> None:
    get_memory_service.cache_clear()
