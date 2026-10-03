"""Fixed-window rate limiting backed by Redis.

Each client gets a counter per scope and per minute (``INCR`` + ``EXPIRE`` in
one transaction). Authenticated requests are counted per user, anonymous ones
per client IP. If Redis is unavailable, requests are allowed (fail open).
"""

import logging
import time

from fastapi import HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.redis import REDIS_ERRORS, get_redis, warn_unavailable
from app.core.security import InvalidTokenError, decode_access_token

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


def client_ip(request: Request) -> str:
    """The caller's IP, taking ``trusted_proxy_hops`` reverse proxies into account.

    With proxies in front, the rightmost ``hops`` entries of X-Forwarded-For were
    written by them; the entry they recorded for the client is the last trusted one.
    Entries further left come from the client itself and are ignored.
    """
    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        chain = [ip.strip() for ip in request.headers.get("x-forwarded-for", "").split(",")]
        chain = [ip for ip in chain if ip]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"


def _client_identity(request: Request, per_user: bool) -> str:
    """``user:<id>`` for a valid bearer token (when ``per_user``), else ``ip:<address>``."""
    if per_user:
        auth = request.headers.get("authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                return f"user:{decode_access_token(token)}"
            except InvalidTokenError:
                pass  # count invalid tokens against the IP
    return f"ip:{client_ip(request)}"


class RateLimit:
    """FastAPI dependency enforcing ``limit_setting`` requests per minute.

    The limit is read from settings on each call, so it can be tuned (and
    overridden in tests) without rebuilding routes.
    """

    def __init__(self, scope: str, limit_setting: str, *, per_user: bool = True) -> None:
        self.scope = scope
        self.limit_setting = limit_setting
        self.per_user = per_user

    async def __call__(self, request: Request, response: Response) -> None:
        settings = get_settings()
        redis = get_redis()
        if not settings.rate_limit_enabled or redis is None:
            return

        limit: int = getattr(settings, self.limit_setting)
        now = time.time()
        window = int(now // WINDOW_SECONDS)
        reset_in = WINDOW_SECONDS - int(now % WINDOW_SECONDS)
        key = f"ratelimit:{self.scope}:{_client_identity(request, self.per_user)}:{window}"

        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, WINDOW_SECONDS + 1)
                count, _ = await pipe.execute()
        except REDIS_ERRORS as exc:
            warn_unavailable(exc)
            return

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(limit - count, 0)),
            "X-RateLimit-Reset": str(reset_in),
        }
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down.",
                headers=headers | {"Retry-After": str(reset_in)},
            )
        response.headers.update(headers)


default_rate_limit = RateLimit("api", "rate_limit_default_per_minute")
auth_rate_limit = RateLimit("auth", "rate_limit_auth_per_minute", per_user=False)
