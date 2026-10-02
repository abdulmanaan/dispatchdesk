"""Shared Redis client.

Redis is an optimisation here (cache, rate limits), never a source of truth.
Callers must treat ``REDIS_ERRORS`` as "Redis unavailable" and carry on.
"""

import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REDIS_ERRORS = (RedisError, OSError)

_client: Redis | None = None
_last_warning = 0.0


def get_redis() -> Redis | None:
    """Return the shared client, or None when Redis is not configured."""
    global _client
    url = get_settings().redis_url
    if not url:
        return None
    if _client is None:
        _client = Redis.from_url(
            url,
            decode_responses=True,
            # Fail fast: a slow Redis must not slow down every request.
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def warn_unavailable(exc: Exception) -> None:
    """Log Redis outages at most once a minute instead of on every request."""
    global _last_warning
    now = time.monotonic()
    if now - _last_warning > 60:
        _last_warning = now
        logger.warning("Redis unavailable, continuing without it: %s", exc)
