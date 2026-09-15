"""FastAPI auth dependencies."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.tokens import (
    AuthPrincipal,
    authenticate_api_key,
    decode_access_token,
    principal_can_access_user,
)
from app.core.config import get_settings
from app.observability.context import set_user_id

_bearer = HTTPBearer(auto_error=False)


def get_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> AuthPrincipal:
    settings = get_settings()
    principal: Optional[AuthPrincipal] = None

    if x_api_key:
        try:
            principal = authenticate_api_key(x_api_key, settings=settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key không hợp lệ.",
            ) from exc
    elif credentials and credentials.scheme.lower() == "bearer":
        try:
            principal = decode_access_token(credentials.credentials, settings=settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ hoặc đã hết hạn.",
            ) from exc

    if principal is None:
        if settings.auth_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Yêu cầu xác thực (Bearer token hoặc X-API-Key).",
                headers={"WWW-Authenticate": "Bearer"},
            )
        principal = AuthPrincipal(subject="anonymous", role="guest", auth_type="none")

    request.state.principal = principal
    if principal.user_id:
        set_user_id(str(principal.user_id))
    return principal


def require_user_access(user_id: UUID, principal: AuthPrincipal = Depends(get_principal)) -> AuthPrincipal:
    if principal.auth_type == "none" and not get_settings().auth_enabled:
        # Dev mode: allow guest UUID access without token.
        return principal
    if not principal_can_access_user(principal, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập tài nguyên của người dùng này.",
        )
    return principal
