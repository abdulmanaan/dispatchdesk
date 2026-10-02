"""Small read-through JSON cache on top of Redis (fails open)."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.redis import REDIS_ERRORS, get_redis, warn_unavailable

KEY_PREFIX = "cache:"


async def get_or_set_json(
    key: str, ttl_seconds: int, loader: Callable[[], Awaitable[Any]]
) -> tuple[Any, bool]:
    """Return ``(value, cache_hit)``.

    On a miss, ``loader`` computes the value, which is stored for ``ttl_seconds``.
    If Redis is unavailable the loader is simply called every time.
    """
    redis = get_redis()
    full_key = KEY_PREFIX + key

    if redis is not None:
        try:
            cached = await redis.get(full_key)
        except REDIS_ERRORS as exc:
            warn_unavailable(exc)
            redis = None
        else:
            if cached is not None:
                return json.loads(cached), True

    value = await loader()

    if redis is not None:
        try:
            await redis.set(full_key, json.dumps(value, default=str), ex=ttl_seconds)
        except REDIS_ERRORS as exc:
            warn_unavailable(exc)
    return value, False
