"""Trip planning and CRUD endpoints (API v1)."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_planning_service
from app.api.schemas.trips import (
    CreateTripRequest,
    ErrorResponse,
    PlanTripRequest,
    TripDetailOut,
    TripListOut,
    TripPlanResponse,
)
from app.auth.deps import get_principal
from app.auth.tokens import AuthPrincipal, principal_can_access_user
from app.core.config import get_settings
from app.observability.errors import capture_exception
from app.services.planning_service import PlanningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Plan a trip from a natural-language request",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def plan_trip(
    payload: PlanTripRequest,
    service: PlanningService = Depends(get_planning_service),
    principal: AuthPrincipal = Depends(get_principal),
) -> TripPlanResponse:
    """Run the travel agent and return a public itinerary (never raw LangGraph state)."""
    settings = get_settings()
    if (
        settings.auth_enabled
        and payload.user_id is not None
        and not principal_can_access_user(principal, payload.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền lập kế hoạch cho người dùng này.",
        )
    try:
        return service.plan(payload)
    except ValueError as exc:
        logger.warning("Trip planning rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        capture_exception(exc, extra={"route": "trips.plan"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lên kế hoạch chuyến đi lúc này.",
        ) from exc


@router.post(
    "",
    response_model=TripDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved trip",
    responses={422: {"model": ErrorResponse}},
)
def create_trip(
    payload: CreateTripRequest,
    service: PlanningService = Depends(get_planning_service),
    principal: AuthPrincipal = Depends(get_principal),
) -> TripDetailOut:
    settings = get_settings()
    if (
        settings.auth_enabled
        and payload.user_id is not None
        and not principal_can_access_user(principal, payload.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền tạo chuyến đi cho người dùng này.",
        )
    return service.create_trip(payload)


@router.get(
    "",
    response_model=TripListOut,
    summary="List saved trips",
)
def list_trips(
    user_id: Optional[UUID] = Query(default=None),
    service: PlanningService = Depends(get_planning_service),
    principal: AuthPrincipal = Depends(get_principal),
) -> TripListOut:
    settings = get_settings()
    if settings.auth_enabled:
        if user_id is None and principal.user_id is not None:
            user_id = principal.user_id
        if user_id is not None and not principal_can_access_user(principal, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền xem danh sách chuyến đi này.",
            )
    return service.list_trips(user_id=user_id)


@router.get(
    "/{trip_id}",
    response_model=TripDetailOut,
    summary="Get a saved trip by ID",
    responses={404: {"model": ErrorResponse}},
)
def get_trip(
    trip_id: UUID,
    service: PlanningService = Depends(get_planning_service),
    principal: AuthPrincipal = Depends(get_principal),
) -> TripDetailOut:
    trip = service.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chuyến đi.")
    settings = get_settings()
    if (
        settings.auth_enabled
        and trip.user_id is not None
        and not principal_can_access_user(principal, trip.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xem chuyến đi này.",
        )
    return trip
