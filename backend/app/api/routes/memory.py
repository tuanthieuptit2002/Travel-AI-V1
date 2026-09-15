"""User travel memory endpoints (structured preferences only)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_memory_service
from app.api.schemas.memory import ErrorResponse, MemoryUpdateBody, UserMemoryOut
from app.auth.deps import require_user_access
from app.auth.tokens import AuthPrincipal
from app.memory.models import MemoryField, MemoryUpdateRequest
from app.memory.service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get(
    "/{user_id}",
    response_model=UserMemoryOut,
    summary="Get structured travel preferences for a user",
)
def get_user_memory(
    user_id: UUID,
    service: MemoryService = Depends(get_memory_service),
    _principal: AuthPrincipal = Depends(require_user_access),
) -> UserMemoryOut:
    memory = service.get_memory(user_id)
    return UserMemoryOut.model_validate(memory.model_dump())


@router.post(
    "/{user_id}",
    response_model=UserMemoryOut,
    summary="Store one validated travel preference",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_user_memory(
    user_id: UUID,
    payload: MemoryUpdateBody,
    service: MemoryService = Depends(get_memory_service),
    _principal: AuthPrincipal = Depends(require_user_access),
) -> UserMemoryOut:
    try:
        memory = service.update_memory(
            MemoryUpdateRequest(
                user_id=user_id,
                field=payload.field,
                value=payload.value,
                evidence=payload.evidence,
                source_excerpt=payload.source_excerpt,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserMemoryOut.model_validate(memory.model_dump())


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete all travel preferences for a user",
)
def clear_user_memory(
    user_id: UUID,
    service: MemoryService = Depends(get_memory_service),
    _principal: AuthPrincipal = Depends(require_user_access),
) -> None:
    service.clear_memory(user_id)


@router.delete(
    "/{user_id}/{field}",
    response_model=UserMemoryOut,
    summary="Delete one preference field",
    responses={400: {"model": ErrorResponse}},
)
def clear_memory_field(
    user_id: UUID,
    field: MemoryField,
    service: MemoryService = Depends(get_memory_service),
    _principal: AuthPrincipal = Depends(require_user_access),
) -> UserMemoryOut:
    memory = service.clear_field(user_id, field)
    return UserMemoryOut.model_validate(memory.model_dump())
