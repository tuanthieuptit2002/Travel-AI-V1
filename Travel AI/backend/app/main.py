from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.api.routes.trips import router as trips_router
from app.auth.routes import router as auth_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.observability.context import get_request_id
from app.observability.errors import capture_exception, init_error_tracking

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json or settings.is_production)
init_error_tracking(settings)

docs_url = None if settings.is_production else "/docs"
redoc_url = None if settings.is_production else "/redoc"
openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "API TripMind AI. Lên kế hoạch du lịch Việt Nam với LangGraph agent dựa trên "
        "công cụ nhà cung cấp. Trạng thái nội bộ của agent không được trả về client."
    ),
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

if settings.trusted_host_list and settings.trusted_host_list != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-ID",
        "Accept",
    ],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "X-Cost-USD", "Retry-After"],
)
app.add_middleware(RequestContextMiddleware)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(trips_router, prefix=settings.api_v1_prefix)
app.include_router(memory_router, prefix=settings.api_v1_prefix)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Yêu cầu không hợp lệ.",
            "code": "validation_error",
            "errors": exc.errors(),
            "request_id": get_request_id(),
        },
        headers={"X-Request-ID": get_request_id() or ""},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    capture_exception(exc, extra={"path": request.url.path, "method": request.method})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Lỗi máy chủ nội bộ.",
            "code": "internal_error",
            "request_id": get_request_id(),
        },
        headers={"X-Request-ID": get_request_id() or ""},
    )


@app.get("/health", tags=["health"])
async def root_health_check() -> dict[str, str]:
    """Convenience liveness endpoint for platform probes."""
    return {"status": "ok", "service": "api"}
