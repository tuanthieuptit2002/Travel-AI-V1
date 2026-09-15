"""JWT and API-key authentication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

Role = Literal["guest", "user", "service", "admin"]


class AuthPrincipal(BaseModel):
    subject: str
    role: Role = "guest"
    user_id: Optional[UUID] = None
    auth_type: Literal["none", "api_key", "jwt"] = "none"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: UUID
    role: Role


def _jwt_module():
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install PyJWT to enable authentication.") from exc
    return jwt


def create_access_token(
    *,
    user_id: UUID,
    role: Role = "guest",
    expires_minutes: Optional[int] = None,
    settings: Optional[Settings] = None,
) -> TokenResponse:
    cfg = settings or get_settings()
    jwt = _jwt_module()
    minutes = expires_minutes or (
        cfg.guest_token_expire_minutes if role == "guest" else cfg.jwt_expire_minutes
    )
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=minutes)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "role": role,
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": uuid4().hex,
    }
    token = jwt.encode(payload, cfg.secret_key, algorithm="HS256")
    return TokenResponse(
        access_token=token,
        expires_in=minutes * 60,
        user_id=user_id,
        role=role,
    )


def decode_access_token(token: str, *, settings: Optional[Settings] = None) -> AuthPrincipal:
    cfg = settings or get_settings()
    jwt = _jwt_module()
    try:
        payload = jwt.decode(
            token,
            cfg.secret_key,
            algorithms=["HS256"],
            audience=cfg.jwt_audience,
            issuer=cfg.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
    user_id = UUID(str(payload.get("user_id") or payload.get("sub")))
    role = payload.get("role") or "guest"
    return AuthPrincipal(
        subject=str(user_id),
        role=role if role in {"guest", "user", "service", "admin"} else "guest",
        user_id=user_id,
        auth_type="jwt",
    )


def authenticate_api_key(api_key: str, *, settings: Optional[Settings] = None) -> AuthPrincipal:
    cfg = settings or get_settings()
    if not api_key or api_key not in cfg.api_key_set:
        raise ValueError("Invalid API key.")
    return AuthPrincipal(
        subject="service",
        role="service",
        user_id=None,
        auth_type="api_key",
    )


def principal_can_access_user(principal: AuthPrincipal, user_id: UUID) -> bool:
    if principal.role in {"service", "admin"}:
        return True
    if principal.user_id is None:
        return False
    return principal.user_id == user_id
