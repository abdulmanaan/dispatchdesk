"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, health, orders
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Release pooled database connections on shutdown."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(orders.router)
    register_error_handlers(app)
    return app


app = create_app()
