"""API schema package."""

from app.api.schemas.trips import (
    CreateTripRequest,
    ErrorResponse,
    PlanTripRequest,
    TripDetailOut,
    TripListOut,
    TripPlanResponse,
    TripSummaryOut,
)

__all__ = [
    "CreateTripRequest",
    "ErrorResponse",
    "PlanTripRequest",
    "TripDetailOut",
    "TripListOut",
    "TripPlanResponse",
    "TripSummaryOut",
]
