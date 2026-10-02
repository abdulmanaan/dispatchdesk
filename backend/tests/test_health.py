"""Tests for the health endpoint."""

from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_database_outage(client: AsyncClient) -> None:
    class BrokenSession:
        async def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def broken_db() -> object:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
