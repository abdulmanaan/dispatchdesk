"""Tests for production/demo deployment features: demo reset, heartbeat."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.demo.heartbeat import LOCK_KEY
from app.demo.seed import seed_demo
from app.models import Order, User
from app.models.enums import OrderStatus, UserRole
from tests.factories import auth_headers, create_business, create_order, create_user

TOKEN = "s3cret-token"


@pytest.fixture
def jobs_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "jobs_token", SecretStr(TOKEN))


@pytest.fixture
def demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)


# --- Demo reset ------------------------------------------------------------------


@pytest.mark.usefixtures("jobs_token", "demo_mode")
async def test_demo_reset_reseeds(client: AsyncClient, db_session: AsyncSession) -> None:
    await seed_demo(db_session)
    visitor_order = await create_order(db_session, await create_business(db_session))
    await db_session.commit()

    response = await client.post("/internal/demo/reset", headers={"X-Jobs-Token": TOKEN})

    assert response.status_code == 200
    assert response.json() == {"users": 14, "orders": 27}
    assert await db_session.scalar(select(func.count()).where(Order.id == visitor_order.id)) == 0


@pytest.mark.usefixtures("jobs_token")
async def test_demo_reset_refused_outside_demo_mode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    response = await client.post("/internal/demo/reset", headers={"X-Jobs-Token": TOKEN})

    assert response.status_code == 404
    assert await db_session.scalar(select(func.count()).where(User.id == user.id)) == 1


@pytest.mark.usefixtures("jobs_token", "demo_mode")
async def test_demo_reset_requires_token(client: AsyncClient) -> None:
    assert (await client.post("/internal/demo/reset")).status_code == 401
    wrong = await client.post("/internal/demo/reset", headers={"X-Jobs-Token": "nope"})
    assert wrong.status_code == 401


@pytest.mark.usefixtures("demo_mode")
async def test_internal_endpoints_hidden_without_token(client: AsyncClient) -> None:
    for path in ("/internal/jobs/run", "/internal/demo/reset"):
        assert (await client.post(path, headers={"X-Jobs-Token": "x"})).status_code == 404


# --- Demo heartbeat --------------------------------------------------------------


async def overdue_candidate(session: AsyncSession) -> tuple[Order, dict[str, str]]:
    """An order past its deadline (not flagged yet) and admin auth headers."""
    order = await create_order(session, await create_business(session))
    await session.execute(
        update(Order)
        .where(Order.id == order.id)
        .values(deliver_by=datetime.now(UTC) - timedelta(minutes=1))
    )
    admin = await create_user(session, UserRole.ADMIN)
    await session.commit()
    return order, auth_headers(admin.id, UserRole.ADMIN)


async def is_overdue(session: AsyncSession, order: Order) -> bool:
    stored = await session.get(Order, order.id, populate_existing=True)
    return bool(stored and stored.is_overdue)


@pytest.mark.usefixtures("demo_mode")
async def test_heartbeat_runs_jobs_on_traffic_once_per_window(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, headers = await overdue_candidate(db_session)

    await client.get("/auth/me", headers=headers)

    assert await is_overdue(db_session, order)  # the background job run flagged it
    ttl = await get_redis().ttl(LOCK_KEY)
    assert 0 < ttl <= 20

    # Within the window, further traffic does not trigger another run.
    later = await create_order(db_session, await create_business(db_session))
    await db_session.execute(
        update(Order)
        .where(Order.id == later.id)
        .values(deliver_by=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db_session.commit()
    await client.get("/auth/me", headers=headers)
    assert not await is_overdue(db_session, later)


async def test_heartbeat_off_outside_demo_mode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, headers = await overdue_candidate(db_session)

    await client.get("/auth/me", headers=headers)

    assert not await is_overdue(db_session, order)
    assert await get_redis().exists(LOCK_KEY) == 0
    assert (await db_session.get(Order, order.id)).status == OrderStatus.PENDING
