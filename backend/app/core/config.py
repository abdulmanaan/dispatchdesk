"""Application settings loaded from environment variables and the .env file."""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://dispatchdesk:dispatchdesk@localhost:5433/dispatchdesk"
    # Echo SQL statements to the log (noisy, useful for debugging).
    database_echo: bool = False

    jwt_secret_key: SecretStr = SecretStr(_DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Default delivery deadline (minutes after creation) when a business omits one.
    default_delivery_window_minutes: int = 60

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
