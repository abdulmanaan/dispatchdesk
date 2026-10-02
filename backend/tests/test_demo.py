"""Tests for the demo data set, one-click demo login and simulated drivers."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.demo.accounts import DEMO_EMAILS, SIMULATED_DOMAIN
from app.demo.seed import seed_demo
from app.demo.simulator import advance_simulated_drivers
from app.jobs.tasks import run_all_jobs
from app.models import AuditLog, Driver, Order, OrderAssignment, User
from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
    OPEN_ASSIGNMENT_STATUSES,
    DriverStatus,
    OrderStatus,
    UserRole,
)
from app.services.dispatch import try_dispatch_order
from tests.factories import add_driver, create_business, create_order, create_user


@pytest.fixture
def demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)


async def count(session: AsyncSession, *where) -> int:
    return await session.scalar(select(func.count()).where(*where)) or 0


# --- Seed ------------------------------------------------------------------------


async def test_seed_creates_consistent_demo_world(db_session: AsyncSession) -> None:
    summary = await seed_demo(db_session)

    assert summary.users == 14  # admin + 4 business owners + 9 drivers
    assert summary.orders == 27
    for role, email in DEMO_EMAILS.items():
        user = await db_session.scalar(select(User).where(User.email == email))
        assert user is not None and user.role == role

    # Every busy driver holds exactly one active order, and vice versa.
    busy = set((await db_session.scalars(select(Driver.id).where(Driver.status == "busy"))).all())
    holders = (
        await db_session.scalars(
            select(Order.driver_id).where(Order.status.in_(ACTIVE_ORDER_STATUSES))
        )
    ).all()
    assert busy == set(holders) and len(holders) == len(set(holders))

    # Every order taken by a driver has an assignment, and open ones are still open.
    for order in (
        await db_session.scalars(select(Order).where(Order.driver_id.is_not(None)))
    ).all():
        assignment = await db_session.scalar(
            select(OrderAssignment).where(OrderAssignment.order_id == order.id)
        )
        assert assignment is not None and assignment.driver_id == order.driver_id
        assert (order.status in ACTIVE_ORDER_STATUSES) == (
            assignment.status in OPEN_ASSIGNMENT_STATUSES
        )

    # Each order has a timeline that starts with its creation.
    created = await count(db_session, AuditLog.action == "order.created")
    assert created == summary.orders
    assert await count(db_session, Order.is_overdue.is_(True)) == 1


async def test_seed_demo_driver_has_an_accepted_order(db_session: AsyncSession) -> None:
    """Visitors logging in as the driver can act right away (and nothing expires)."""
    await seed_demo(db_session)
    order = await db_session.scalar(
        select(Order)
        .join(Driver, Driver.id == Order.driver_id)
        .join(User, User.id == Driver.user_id)
        .where(User.email == DEMO_EMAILS[UserRole.DRIVER])
        .where(Order.status == OrderStatus.ASSIGNED)
    )
    assert order is not None and order.accepted_at is not None


async def test_seed_is_idempotent_and_reset_rebuilds(db_session: AsyncSession) -> None:
    await seed_demo(db_session)
    again = await seed_demo(db_session)
    assert again.skipped
    assert await count(db_session, User.id.is_not(None)) == 14

    extra = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()
    rebuilt = await seed_demo(db_session, reset=True)

    assert not rebuilt.skipped
    assert await count(db_session, User.id == extra.id) == 0
    assert await count(db_session, User.id.is_not(None)) == 14


# --- Demo login ------------------------------------------------------------------


async def test_demo_disabled_by_default(client: AsyncClient, db_session: AsyncSession) -> None:
    await seed_demo(db_session)

    info = await client.get("/auth/demo")
    login = await client.post("/auth/demo-login", json={"role": "admin"})

    assert info.json() == {"enabled": False, "accounts": []}
    assert login.status_code == 404


@pytest.mark.usefixtures("demo_mode")
async def test_demo_not_offered_until_seeded(client: AsyncClient) -> None:
    assert (await client.get("/auth/demo")).json()["enabled"] is False
    assert (await client.post("/auth/demo-login", json={"role": "driver"})).status_code == 404


@pytest.mark.usefixtures("demo_mode")
@pytest.mark.parametrize("role", ["admin", "business", "driver"])
async def test_demo_login_per_role(
    client: AsyncClient, db_session: AsyncSession, role: str
) -> None:
    await seed_demo(db_session)

    info = (await client.get("/auth/demo")).json()
    response = await client.post("/auth/demo-login", json={"role": role})

    assert info["enabled"] is True
    assert [a["role"] for a in info["accounts"]] == ["admin", "business", "driver"]
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == role
    assert me.json()["email"] == DEMO_EMAILS[UserRole(role)]


# --- Simulated drivers -----------------------------------------------------------


async def sim_driver(session: AsyncSession, km: float = 1):
    user = await create_user(session, UserRole.DRIVER, email=f"sim{km}@{SIMULATED_DOMAIN}")
    driver = await add_driver(session, km)
    # Re-point the factory's driver profile to the simulated user.
    await session.execute(update(Driver).where(Driver.id == driver.id).values(user_id=user.id))
    return driver


async def age(session: AsyncSession, order_id, **seconds_ago: int) -> None:
    now = datetime.now(UTC)
    values = {field: now - timedelta(seconds=s) for field, s in seconds_ago.items()}
    await session.execute(update(Order).where(Order.id == order_id).values(**values))
    await session.commit()


async def test_simulated_driver_works_through_an_order(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await sim_driver(db_session)
    order = await create_order(db_session, business)
    await db_session.commit()
    await try_dispatch_order(db_session, order.id)

    assert await advance_simulated_drivers(db_session) == 0  # just assigned: waits a bit

    await age(db_session, order.id, assigned_at=30)
    assert await advance_simulated_drivers(db_session) == 1
    await age(db_session, order.id, accepted_at=60)
    assert await advance_simulated_drivers(db_session) == 1
    await age(db_session, order.id, picked_up_at=120)
    assert await advance_simulated_drivers(db_session) == 1

    stored = await db_session.get(Order, order.id, populate_existing=True)
    assert stored.status == OrderStatus.DELIVERED
    assert (await db_session.get(Driver, driver.id, populate_existing=True)).status == (
        DriverStatus.AVAILABLE
    )
    actions = (
        await db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == str(order.id)).order_by(AuditLog.id)
        )
    ).all()
    assert actions == ["order.assigned", "order.accepted", "order.picked_up", "order.delivered"]


async def test_real_drivers_are_never_simulated(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await add_driver(db_session, 1)  # a normal driver account
    order = await create_order(db_session, business)
    await db_session.commit()
    await try_dispatch_order(db_session, order.id)
    await age(db_session, order.id, assigned_at=600)

    assert await advance_simulated_drivers(db_session) == 0
    assert (await db_session.get(Order, order.id, populate_existing=True)).accepted_at is None


async def test_simulator_runs_before_expiry_in_demo_mode(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a slow scheduler, simulated offers must be accepted, not expired."""
    business = await create_business(db_session)
    await sim_driver(db_session)
    order = await create_order(db_session, business)
    await db_session.commit()
    await try_dispatch_order(db_session, order.id)
    await age(db_session, order.id, assigned_at=600)  # past the 3-minute timeout

    monkeypatch.setattr(get_settings(), "demo_mode", True)
    report = await run_all_jobs(db_session)

    assert report.simulated_steps == 1
    assert report.expired_assignments == 0
    assert (await db_session.get(Order, order.id, populate_existing=True)).accepted_at is not None


async def test_simulator_is_off_outside_demo_mode(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await sim_driver(db_session)
    order = await create_order(db_session, business)
    await db_session.commit()
    await try_dispatch_order(db_session, order.id)
    await age(db_session, order.id, assigned_at=600)

    report = await run_all_jobs(db_session)

    assert report.simulated_steps == 0
    assert report.expired_assignments == 1
