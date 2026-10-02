"""Tests for auto-dispatch: driver selection, triggers and concurrency safety."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, Driver, Order, OrderAssignment
from app.models.enums import AssignmentStatus, DriverStatus, OrderStatus, UserRole
from app.services.dispatch import DispatchOutcome, dispatch_pending_orders, try_dispatch_order
from app.services.geo import KM_PER_DEGREE_LAT
from tests.factories import (
    auth_headers,
    business_headers,
    create_business,
    create_driver,
    create_order,
    create_user,
    driver_headers,
)

# Pickup at Liberty Market (factory default). Driver positions are offsets from it:
# one degree of latitude is roughly 111 km.
PICKUP_LAT, PICKUP_LNG = 31.5104, 74.3416


def at_km_north(km: float) -> dict[str, float]:
    return {"current_lat": PICKUP_LAT + km / KM_PER_DEGREE_LAT, "current_lng": PICKUP_LNG}


async def fresh(session: AsyncSession, model: type, obj_id: object):
    return await session.get(model, obj_id, populate_existing=True)


async def add_driver(session: AsyncSession, km: float, **overrides: object) -> Driver:
    """An available driver ``km`` north of the pickup with a fresh location."""
    values = {"location_updated_at": datetime.now(UTC), **at_km_north(km)} | overrides
    return await create_driver(session, **values)


async def add_completed_deliveries(session: AsyncSession, driver: Driver, count: int) -> None:
    business = await create_business(session)
    now = datetime.now(UTC)
    for _ in range(count):
        order = await create_order(
            session,
            business,
            status=OrderStatus.DELIVERED,
            driver_id=driver.id,
            assigned_at=now,
            accepted_at=now,
            picked_up_at=now,
            delivered_at=now,
        )
        session.add(
            OrderAssignment(
                order_id=order.id,
                driver_id=driver.id,
                status=AssignmentStatus.COMPLETED,
                ended_at=now - timedelta(minutes=30),
            )
        )
    await session.flush()


# --- Selection rules -------------------------------------------------------------


async def test_assigns_nearest_available_driver(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    far = await add_driver(db_session, 5)
    near = await add_driver(db_session, 1)
    order = await create_order(db_session, business)
    await db_session.commit()

    result = await try_dispatch_order(db_session, order.id)

    assert result.outcome == DispatchOutcome.ASSIGNED
    assert result.driver_id == near.id
    assert result.distance_km == pytest.approx(1.0, abs=0.01)
    assert result.candidates == 2

    stored = await fresh(db_session, Order, order.id)
    assert stored.status == OrderStatus.ASSIGNED and stored.driver_id == near.id
    assert stored.assignment_attempts == 1 and stored.accepted_at is None
    assert (await fresh(db_session, Driver, near.id)).status == DriverStatus.BUSY
    assert (await fresh(db_session, Driver, far.id)).status == DriverStatus.AVAILABLE

    assignment = await db_session.scalar(
        select(OrderAssignment).where(OrderAssignment.order_id == order.id)
    )
    assert assignment.status == AssignmentStatus.OFFERED and assignment.driver_id == near.id

    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "order.assigned"))
    assert audit.actor_id is None  # automatic dispatch
    assert audit.details["driver_id"] == str(near.id)
    assert audit.details["candidates"] == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": DriverStatus.OFFLINE},
        {"status": DriverStatus.BUSY},
        {"current_lat": None, "current_lng": None, "location_updated_at": None},
        {"location_updated_at": datetime.now(UTC) - timedelta(hours=3)},  # stale location
        at_km_north(20),  # outside the 15 km radius
    ],
    ids=["offline", "busy", "no-location", "stale-location", "too-far"],
)
async def test_ineligible_drivers_are_skipped(
    db_session: AsyncSession, overrides: dict[str, object]
) -> None:
    business = await create_business(db_session)
    values = {**at_km_north(1), "location_updated_at": datetime.now(UTC)} | overrides
    driver = await create_driver(db_session, **values)
    order = await create_order(db_session, business)
    await db_session.commit()

    result = await try_dispatch_order(db_session, order.id)

    assert result.outcome == DispatchOutcome.NO_DRIVER
    assert (await fresh(db_session, Order, order.id)).status == OrderStatus.PENDING
    assert (await fresh(db_session, Driver, driver.id)).status == overrides.get(
        "status", DriverStatus.AVAILABLE
    )


async def test_stale_location_check_can_be_disabled(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "dispatch_location_max_age_minutes", 0)
    business = await create_business(db_session)
    await add_driver(db_session, 1, location_updated_at=datetime.now(UTC) - timedelta(days=30))
    order = await create_order(db_session, business)
    await db_session.commit()

    assert (await try_dispatch_order(db_session, order.id)).outcome == DispatchOutcome.ASSIGNED


async def test_workload_spreads_orders_fairly(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    hardworking = await add_driver(db_session, 1.0)  # 1.0 km + 3 deliveries * 1.0 = 4.0
    rested = await add_driver(db_session, 2.5)  # 2.5 km + 0 = 2.5
    await add_completed_deliveries(db_session, hardworking, 3)
    order = await create_order(db_session, business)
    await db_session.commit()

    result = await try_dispatch_order(db_session, order.id)

    assert result.driver_id == rested.id


async def test_driver_who_let_order_expire_is_not_reoffered(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    slow = await add_driver(db_session, 0.5)
    other = await add_driver(db_session, 3)
    order = await create_order(db_session, business)
    db_session.add(
        OrderAssignment(order_id=order.id, driver_id=slow.id, status=AssignmentStatus.EXPIRED)
    )
    await db_session.commit()

    result = await try_dispatch_order(db_session, order.id)

    assert result.driver_id == other.id


async def test_non_pending_and_missing_orders(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await add_driver(db_session, 1)
    order = await create_order(
        db_session,
        business,
        status=OrderStatus.FAILED,
        failure_reason="x",
        failed_at=datetime.now(UTC),
    )
    await db_session.commit()

    assert (await try_dispatch_order(db_session, order.id)).outcome == DispatchOutcome.NOT_PENDING
    assert (await try_dispatch_order(db_session, uuid.uuid4())).outcome == DispatchOutcome.NOT_FOUND


async def test_pending_orders_dispatched_most_urgent_first(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1)
    now = datetime.now(UTC)
    relaxed = await create_order(db_session, business, deliver_by=now + timedelta(hours=2))
    urgent = await create_order(db_session, business, deliver_by=now + timedelta(minutes=15))
    await db_session.commit()

    results = await dispatch_pending_orders(db_session)

    assigned = [r for r in results if r.outcome == DispatchOutcome.ASSIGNED]
    assert [(r.order_id, r.driver_id) for r in assigned] == [(urgent.id, driver.id)]
    assert (await fresh(db_session, Order, relaxed.id)).status == OrderStatus.PENDING


# --- Concurrency -----------------------------------------------------------------


async def test_concurrent_dispatch_never_double_books_a_driver(db_session: AsyncSession) -> None:
    """Many orders dispatched at once, fewer drivers: each driver gets at most one."""
    business = await create_business(db_session)
    drivers = [await add_driver(db_session, km) for km in (0.5, 1.0, 1.5)]
    orders = [await create_order(db_session, business) for _ in range(10)]
    await db_session.commit()

    async def dispatch_in_own_session(order_id):
        async with SessionLocal() as session:
            return await try_dispatch_order(session, order_id)

    results = await asyncio.gather(*(dispatch_in_own_session(o.id) for o in orders))

    outcomes = [r.outcome for r in results]
    assert DispatchOutcome.CONFLICT not in outcomes  # locks prevented it, not the index
    assert outcomes.count(DispatchOutcome.ASSIGNED) == len(drivers)
    assigned_drivers = [r.driver_id for r in results if r.driver_id]
    assert sorted(map(str, assigned_drivers)) == sorted(str(d.id) for d in drivers)

    active_per_driver = (
        await db_session.execute(
            select(Order.driver_id, func.count())
            .where(Order.status == OrderStatus.ASSIGNED)
            .group_by(Order.driver_id)
        )
    ).all()
    assert all(count == 1 for _, count in active_per_driver)
    pending = await db_session.scalar(
        select(func.count()).where(Order.status == OrderStatus.PENDING)
    )
    assert pending == len(orders) - len(drivers)


async def test_concurrent_dispatch_of_same_order_assigns_once(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    for km in (0.5, 1.0, 1.5):
        await add_driver(db_session, km)
    order = await create_order(db_session, business)
    await db_session.commit()

    async def dispatch_in_own_session():
        async with SessionLocal() as session:
            return await try_dispatch_order(session, order.id)

    results = await asyncio.gather(*(dispatch_in_own_session() for _ in range(5)))

    outcomes = [r.outcome for r in results]
    assert outcomes.count(DispatchOutcome.ASSIGNED) == 1
    # The order lock must stop the duplicates; the unique index is only a backstop.
    assert DispatchOutcome.CONFLICT not in outcomes
    stored = await fresh(db_session, Order, order.id)
    assert stored.assignment_attempts == 1
    busy = await db_session.scalar(select(func.count()).where(Driver.status == DriverStatus.BUSY))
    assert busy == 1


async def test_driver_locked_elsewhere_is_skipped_not_waited_for(db_session: AsyncSession) -> None:
    """SKIP LOCKED: a driver held by another transaction is passed over immediately."""
    business = await create_business(db_session)
    nearest = await add_driver(db_session, 0.5)
    runner_up = await add_driver(db_session, 2)
    order = await create_order(db_session, business)
    await db_session.commit()

    async with SessionLocal() as other_tx, SessionLocal() as dispatch_tx:
        # Another transaction (e.g. a parallel dispatch) holds the nearest driver.
        await other_tx.get(Driver, nearest.id, with_for_update=True)

        result = await asyncio.wait_for(try_dispatch_order(dispatch_tx, order.id), timeout=2)

        await other_tx.rollback()

    assert result.driver_id == runner_up.id


async def test_order_locked_elsewhere_is_skipped(db_session: AsyncSession) -> None:
    """An order being cancelled (row locked) is skipped rather than waited for."""
    business = await create_business(db_session)
    await add_driver(db_session, 1)
    order = await create_order(db_session, business)
    await db_session.commit()

    async with SessionLocal() as other_tx, SessionLocal() as dispatch_tx:
        await other_tx.get(Order, order.id, with_for_update=True)

        result = await asyncio.wait_for(try_dispatch_order(dispatch_tx, order.id), timeout=2)

        await other_tx.rollback()

    assert result.outcome == DispatchOutcome.LOCKED


# --- Triggers through the API ----------------------------------------------------


async def test_new_order_is_dispatched_immediately(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1)
    await db_session.commit()

    response = await client.post(
        "/orders",
        json={
            "customer_name": "Fatima Noor",
            "customer_phone": "+923001112233",
            "dropoff_address": "Garden Town, Lahore",
            "dropoff_lat": 31.5000,
            "dropoff_lng": 74.3200,
        },
        headers=business_headers(business),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "assigned"
    assert response.json()["driver_id"] == str(driver.id)


async def test_driver_going_available_receives_waiting_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1, status=DriverStatus.OFFLINE)
    order = await create_order(db_session, business)
    await db_session.commit()

    response = await client.put(
        "/drivers/me/status", json={"status": "available"}, headers=driver_headers(driver)
    )

    assert response.json()["status"] == "busy"
    current = await client.get("/drivers/me/order", headers=driver_headers(driver))
    assert current.json()["id"] == str(order.id)


async def test_driver_gets_next_order_after_delivering(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1)
    first = await create_order(db_session, business)
    await db_session.commit()
    await try_dispatch_order(db_session, first.id)
    second = await create_order(db_session, business)  # waits: the only driver is busy
    await db_session.commit()
    headers = driver_headers(driver)

    for action in ("accept", "pickup", "deliver"):
        response = await client.post(f"/orders/{first.id}/{action}", headers=headers)
        assert response.status_code == 200, response.text

    assert response.json()["status"] == "delivered"
    current = await client.get("/drivers/me/order", headers=headers)
    assert current.json()["id"] == str(second.id)


async def test_admin_manual_dispatch(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()
    headers = auth_headers(admin.id, UserRole.ADMIN)

    nobody = await client.post(f"/dispatch/orders/{order.id}", headers=headers)
    assert nobody.json()["result"]["outcome"] == "no_driver"
    assert nobody.json()["order"]["status"] == "pending"

    driver = await add_driver(db_session, 2)
    await db_session.commit()
    assigned = await client.post(f"/dispatch/orders/{order.id}", headers=headers)
    assert assigned.json()["result"]["outcome"] == "assigned"
    assert assigned.json()["order"]["driver_id"] == str(driver.id)

    again = await client.post(f"/dispatch/orders/{order.id}", headers=headers)
    assert again.status_code == 409

    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "order.assigned"))
    assert audit.actor_id == admin.id


async def test_admin_dispatch_run(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    for _ in range(3):
        await create_order(db_session, business)
    await add_driver(db_session, 1)
    await add_driver(db_session, 2)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    response = await client.post("/dispatch/run", headers=auth_headers(admin.id, UserRole.ADMIN))

    assert response.status_code == 200
    assert response.json()["attempted"] == 3
    assert response.json()["assigned"] == 2


async def test_dispatch_endpoints_are_admin_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)
    await db_session.commit()

    assert (
        await client.post(f"/dispatch/orders/{order.id}", headers=business_headers(business))
    ).status_code == 403
    assert (
        await client.post("/dispatch/run", headers=business_headers(business))
    ).status_code == 403
