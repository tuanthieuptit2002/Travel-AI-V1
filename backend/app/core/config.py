"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Secrets must come from the environment — never hardcode."""

    app_env: str = "development"
    app_name: str = "TripMind AI API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://tripmind:tripmind@localhost:5432/tripmind"
    embedding_dimensions: int = 1536
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    trusted_hosts: str = "*"

    # Auth / secrets
    auth_enabled: bool = False
    secret_key: str = "dev-only-change-me-tripmind-secret-key-32chars"
    api_keys: str = ""  # comma-separated service API keys
    jwt_issuer: str = "tripmind-ai"
    jwt_audience: str = "tripmind-api"
    jwt_expire_minutes: int = 60 * 24
    guest_token_expire_minutes: int = 60 * 12

    # Database pool
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    rate_limit_plan_requests: int = 10
    rate_limit_plan_window_seconds: int = 60

    # Redis cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cache_weather_ttl_seconds: int = 600
    cache_places_ttl_seconds: int = 900

    # Travel providers
    travel_data_mode: str = "mock"
    google_maps_api_key: str = ""
    open_meteo_base_url: str = "https://api.open-meteo.com"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com"
    provider_http_timeout_seconds: float = 10.0
    provider_http_max_retries: int = 3
    provider_http_backoff_seconds: float = 0.5

    # LLM / embeddings
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    knowledge_root: str = "../knowledge"
    rag_top_k: int = 5

    # Agent guards
    agent_max_iterations: int = 16
    agent_timeout_seconds: float = 45.0
    agent_max_repair_attempts: int = 1
    agent_max_tool_calls: int = 80

    # Observability / error tracking
    log_json: bool = False
    log_level: str = "INFO"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    # Cost tracking (USD estimates; override via env if needed)
    cost_openai_embedding_per_1k: float = 0.00002
    cost_openai_chat_input_per_1k: float = 0.00015
    cost_openai_chat_output_per_1k: float = 0.0006

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().casefold() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> List[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def api_key_set(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    @field_validator("travel_data_mode")
    @classmethod
    def validate_travel_mode(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"mock", "live"}:
            raise ValueError("TRAVEL_DATA_MODE must be 'mock' or 'live'")
        return normalized

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if not self.is_production:
            return self
        weak_markers = (
            "change-me",
            "dev-only",
            "tripmind:tripmind",
            "password",
            "secret-key-32chars",
        )
        if any(marker in self.secret_key.casefold() for marker in weak_markers):
            raise ValueError("SECRET_KEY must be a strong unique value in production.")
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production.")
        if self.auth_enabled and not self.api_key_set:
            raise ValueError("API_KEYS must be set when AUTH_ENABLED=true in production.")
        if "localhost" in self.cors_origins and self.is_production:
            # Allow empty override via explicit CORS_ORIGINS without localhost.
            pass
        if self.travel_data_mode == "live" and not self.google_maps_api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY is required when TRAVEL_DATA_MODE=live.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
