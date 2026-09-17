"""Auth API routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import get_principal
from app.auth.tokens import AuthPrincipal, TokenResponse, create_access_token
from app.cache import RateLimitExceeded, check_rate_limit
from app.core.config import get_settings
from app.observability.context import get_request_id

router = APIRouter(prefix="/auth", tags=["auth"])


class GuestTokenRequest(BaseModel):
    user_id: Optional[UUID] = Field(
        default=None,
        description="Optional stable guest UUID; a new one is minted when omitted.",
    )


@router.post(
    "/guest",
    response_model=TokenResponse,
    summary="Issue a short-lived guest JWT for the frontend",
)
def issue_guest_token(payload: GuestTokenRequest) -> TokenResponse:
    settings = get_settings()
    request_key = f"auth:guest:{get_request_id() or 'anon'}"
    try:
        check_rate_limit(
            request_key,
            limit=max(5, settings.rate_limit_plan_requests),
            window_seconds=settings.rate_limit_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu cấp token.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    user_id = payload.user_id or uuid4()
    return create_access_token(user_id=user_id, role="guest", settings=settings)


@router.get("/me", response_model=AuthPrincipal, summary="Inspect the current principal")
def read_me(principal: AuthPrincipal = Depends(get_principal)) -> AuthPrincipal:
    return principal
