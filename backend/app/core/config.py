"""Application settings loaded from environment variables and the .env file."""

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Development-only fallback. Production must set JWT_SECRET_KEY explicitly.
_DEV_JWT_SECRET = "dev-insecure-secret-change-me-in-production"

# libpq query parameters that asyncpg does not understand.
_UNSUPPORTED_ASYNCPG_PARAMS = {"sslmode", "channel_binding"}


def normalize_database_url(url: str) -> str:
    """Convert a standard Postgres URL into one usable by SQLAlchemy + asyncpg.

    Hosted providers such as Neon hand out URLs like
    ``postgresql://user:pass@host/db?sslmode=require&channel_binding=require``.
    asyncpg needs the ``postgresql+asyncpg`` scheme and an ``ssl`` parameter
    instead of the libpq-specific ``sslmode`` / ``channel_binding``.
    """
    parts = urlsplit(url)

    scheme = parts.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+asyncpg"

    params = dict(parse_qsl(parts.query))
    sslmode = params.get("sslmode")
    params = {k: v for k, v in params.items() if k not in _UNSUPPORTED_ASYNCPG_PARAMS}
    if sslmode and sslmode != "disable" and "ssl" not in params:
        params["ssl"] = "require"

    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DispatchDesk API"
    # Browser origins allowed to call the API (the frontend). Comma-separated in env.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://dispatchdesk:dispatchdesk@localhost:5433/dispatchdesk"
    # Echo SQL statements to the log (noisy, useful for debugging).
    database_echo: bool = False

    # Redis for caching and rate limiting. Unset (or unreachable) means both features
    # are skipped and requests still succeed. Upstash "rediss://" URLs work too.
    redis_url: str | None = "redis://localhost:6379/0"
    cache_stats_ttl_seconds: int = 10

    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 120
    # Login and registration, per client IP.
    rate_limit_auth_per_minute: int = 10
    # Use the first X-Forwarded-For address as the client IP. Enable only behind a
    # trusted reverse proxy, otherwise clients can spoof their IP.
    trust_forwarded_for: bool = False

    jwt_secret_key: SecretStr = SecretStr(_DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Default delivery deadline (minutes after creation) when a business omits one.
    default_delivery_window_minutes: int = 60

    # --- Auto-dispatch tuning ---
    # Only drivers within this distance of the pickup are considered.
    dispatch_max_radius_km: float = 15.0
    # Ignore drivers whose last location is older than this. 0 disables the check
    # (useful for a demo deployment where seeded locations never move).
    dispatch_location_max_age_minutes: int = 60
    # Fairness: each delivery completed within this window adds a penalty, expressed
    # as extra kilometres, so a slightly farther but less busy driver can win.
    dispatch_workload_window_hours: int = 8
    dispatch_workload_penalty_km: float = 1.0

    # --- Background jobs ---
    # An assigned order not accepted within this time is taken back and reassigned.
    acceptance_timeout_seconds: int = 180
    # How often the local worker runs the jobs.
    jobs_interval_seconds: int = 30
    # Max orders each job handles per run (keeps one run short).
    jobs_batch_size: int = 50
    # Shared secret for POST /internal/jobs/run (used by an external scheduler in
    # production). The endpoint is disabled while this is unset.
    jobs_token: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        secret = self.jwt_secret_key.get_secret_value()
        if self.environment == "production" and (secret == _DEV_JWT_SECRET or len(secret) < 32):
            raise ValueError("JWT_SECRET_KEY must be set to a random value of 32+ characters")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
