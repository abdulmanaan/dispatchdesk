"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit_logs, auth, dispatch, drivers, health, internal, orders, stats
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import default_rate_limit
from app.core.redis import close_redis
from app.db.session import engine
from app.demo.heartbeat import demo_heartbeat


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Release pooled database and Redis connections on shutdown."""
    yield
    await engine.dispose()
    await close_redis()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
        # Let the browser read rate-limit and cache headers.
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After", "X-Cache"],
    )
    # Health checks and the token-protected jobs endpoint are not rate limited.
    app.include_router(health.router)
    app.include_router(internal.router)

    # The demo heartbeat is a no-op unless DEMO_MODE is on.
    public = [Depends(default_rate_limit), Depends(demo_heartbeat)]
    for module in (auth, orders, drivers, dispatch, stats, audit_logs):
        app.include_router(module.router, dependencies=public)
    register_error_handlers(app)
    return app


app = create_app()
