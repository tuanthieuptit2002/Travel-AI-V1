"""HTTP route definitions."""

from app.api.routes.health import router as health_router
from app.api.routes.trips import router as trips_router

__all__ = ["health_router", "trips_router"]
