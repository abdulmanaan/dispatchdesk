"""Shared pytest fixtures.

Tests run against a separate database (``dispatchdesk_test`` by default).
The environment is configured here, before any ``app`` module is imported,
so the cached settings and the engine pick up the test database URL.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://dispatchdesk:dispatchdesk@localhost:5433/dispatchdesk_test",
)

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client that calls the ASGI app in-process."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
