"""Tests for the background jobs, the worker loop and the cron endpoint."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs import worker
from app.jobs.tasks import JobReport, flag_overdue_orders, run_all_jobs
from app.models import AuditLog, Driver, Order, OrderAssignment
from app.models.enums import AssignmentStatus, DriverStatus, OrderStatus
from app.services.dispatch import try_dispatch_order
from tests.factories import add_driver, create_business, create_order, driver_headers


async def fresh(session: AsyncSession, model: type, obj_id: object):
    return await session.get(model, obj_id, populate_existing=True)


async def dispatched_order(session: AsyncSession, *, minutes_ago: float) -> tuple[Order, Driver]:
    """An order assigned (not accepted) to a nearby driver ``minutes_ago`` minutes ago."""
    business = await create_business(session)
    driver = await add_driver(session, 1)
    order = await create_order(session, business)
    await session.commit()
    result = await try_dispatch_order(session, order.id)
    assert result.driver_id == driver.id

    assigned_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    await session.execute(update(Order).where(Order.id == order.id).values(assigned_at=assigned_at))
    await session.execute(
        update(OrderAssignment)
        .where(OrderAssignment.order_id == order.id)
        .values(assigned_at=assigned_at)
    )
    await session.commit()
    return order, driver


# --- Expire unaccepted assignments -----------------------------------------------


async def test_unaccepted_order_is_reassigned_to_another_driver(db_session: AsyncSession) -> None:
    order, slow_driver = await dispatched_order(db_session, minutes_ago=10)
    backup = await add_driver(db_session, 3)
    await db_session.commit()

    report = await run_all_jobs(db_session)

    assert report.expired_assignments == 1
    assert report.reassigned == 1
    stored = await fresh(db_session, Order, order.id)
    assert stored.status == OrderStatus.ASSIGNED
    assert stored.driver_id == backup.id
    assert stored.assignment_attempts == 2

    # The slow driver is taken offline and their attempt is recorded as expired.
    assert (await fresh(db_session, Driver, slow_driver.id)).status == DriverStatus.OFFLINE
    assert (await fresh(db_session, Driver, backup.id)).status == DriverStatus.BUSY
    history = (
        await db_session.execute(
            select(OrderAssignment.driver_id, OrderAssignment.status)
            .where(OrderAssignment.order_id == order.id)
            .order_by(OrderAssignment.assigned_at)
        )
    ).all()
    assert history == [
        (slow_driver.id, AssignmentStatus.EXPIRED),
        (backup.id, AssignmentStatus.OFFERED),
    ]

    actions = set(
        (await db_session.scalars(select(AuditLog.action).where(AuditLog.actor_id.is_(None)))).all()
    )
    assert {"order.assignment_expired", "driver.status_changed", "order.assigned"} <= actions


async def test_expired_order_waits_when_no_other_driver(db_session: AsyncSession) -> None:
    order, slow_driver = await dispatched_order(db_session, minutes_ago=10)

    report = await run_all_jobs(db_session)

    assert (report.expired_assignments, report.reassigned) == (1, 0)
    stored = await fresh(db_session, Order, order.id)
    assert stored.status == OrderStatus.PENDING and stored.driver_id is None

    # Even if the slow driver comes back online, this order is not offered to them again.
    slow = await fresh(db_session, Driver, slow_driver.id)
    slow.status = DriverStatus.AVAILABLE
    await db_session.commit()
    await run_all_jobs(db_session)
    assert (await fresh(db_session, Order, order.id)).status == OrderStatus.PENDING


@pytest.mark.parametrize("minutes_ago", [0, 2.5])
async def test_recent_assignment_is_left_alone(
    db_session: AsyncSession, minutes_ago: float
) -> None:
    order, driver = await dispatched_order(db_session, minutes_ago=minutes_ago)  # timeout is 3 min

    report = await run_all_jobs(db_session)

    assert report.expired_assignments == 0
    assert (await fresh(db_session, Order, order.id)).driver_id == driver.id


async def test_accepted_assignment_never_expires(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, driver = await dispatched_order(db_session, minutes_ago=1)
    await client.post(f"/orders/{order.id}/accept", headers=driver_headers(driver))
    await db_session.execute(
        update(Order)
        .where(Order.id == order.id)
        .values(assigned_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.commit()

    report = await run_all_jobs(db_session)

    assert report.expired_assignments == 0
    assert (await fresh(db_session, Order, order.id)).driver_id == driver.id


async def test_expiry_skips_order_locked_by_driver_accepting(db_session: AsyncSession) -> None:
    """If the driver is accepting right now (order row locked), the job leaves it alone."""
    order, driver = await dispatched_order(db_session, minutes_ago=10)

    async with SessionLocal() as accepting_tx:
        await accepting_tx.get(Order, order.id, with_for_update=True)  # driver's accept in flight

        report = await asyncio.wait_for(run_all_jobs(db_session), timeout=3)

        await accepting_tx.rollback()

    assert report.expired_assignments == 0
    assert (await fresh(db_session, Order, order.id)).driver_id == driver.id


async def test_late_accept_after_expiry_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, slow_driver = await dispatched_order(db_session, minutes_ago=10)
    await run_all_jobs(db_session)

    response = await client.post(f"/orders/{order.id}/accept", headers=driver_headers(slow_driver))

    assert response.status_code == 404  # the order is no longer theirs


# --- Pending retry and overdue ---------------------------------------------------


async def test_pending_orders_are_retried(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)  # created while nobody was free
    await db_session.commit()
    driver = await add_driver(db_session, 2)
    await db_session.commit()

    report = await run_all_jobs(db_session)

    assert report.dispatched_pending == 1
    assert (await fresh(db_session, Order, order.id)).driver_id == driver.id


async def test_flag_overdue_orders(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1, status=DriverStatus.OFFLINE)
    past = datetime.now(UTC) - timedelta(minutes=5)
    now = datetime.now(UTC)
    late_pending = await create_order(db_session, business, deliver_by=past)
    late_in_transit = await create_order(
        db_session,
        business,
        deliver_by=past,
        status=OrderStatus.PICKED_UP,
        driver_id=driver.id,
        assigned_at=now,
        accepted_at=now,
        picked_up_at=now,
    )
    on_time = await create_order(db_session, business)
    late_but_delivered = await create_order(
        db_session,
        business,
        deliver_by=past,
        status=OrderStatus.DELIVERED,
        driver_id=driver.id,
        assigned_at=now,
        accepted_at=now,
        delivered_at=now,
    )
    await db_session.commit()

    report = JobReport()
    await flag_overdue_orders(db_session, report)
    await flag_overdue_orders(db_session, report)  # second run must not flag again

    assert report.flagged_overdue == 2
    flagged = {
        o.id
        for o in (await db_session.scalars(select(Order).where(Order.is_overdue.is_(True)))).all()
    }
    assert flagged == {late_pending.id, late_in_transit.id}
    assert on_time.id not in flagged and late_but_delivered.id not in flagged
    audits = await db_session.scalar(select(func.count()).where(AuditLog.action == "order.overdue"))
    assert audits == 2


# --- Robustness ------------------------------------------------------------------


async def test_parallel_runners_handle_each_order_once(db_session: AsyncSession) -> None:
    """The local worker and the cron endpoint may overlap; work must not be duplicated."""
    business = await create_business(db_session)
    orders = []
    for km in (1, 2, 3, 4):
        await add_driver(db_session, km)
        orders.append(await create_order(db_session, business))
    await db_session.commit()
    for order in orders:
        await try_dispatch_order(db_session, order.id)
    await db_session.execute(
        update(Order).values(assigned_at=datetime.now(UTC) - timedelta(minutes=10))
    )
    await db_session.commit()

    async def runner() -> JobReport:
        async with SessionLocal() as session:
            return await run_all_jobs(session)

    reports = await asyncio.gather(*(runner() for _ in range(3)))

    assert sum(r.expired_assignments for r in reports) == len(orders)
    expired = await db_session.scalar(
        select(func.count()).where(OrderAssignment.status == AssignmentStatus.EXPIRED)
    )
    assert expired == len(orders)


async def test_one_failing_job_does_not_stop_the_others(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    business = await create_business(db_session)
    await create_order(db_session, business, deliver_by=datetime.now(UTC) - timedelta(minutes=1))
    await db_session.commit()

    async def broken(*_args: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.jobs.tasks.dispatch_pending_orders", broken)

    report = await run_all_jobs(db_session)

    assert report.flagged_overdue == 1


async def test_worker_runs_until_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    stop = asyncio.Event()

    async def fake_run_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            stop.set()
        if calls == 2:
            raise RuntimeError("database hiccup")  # must not kill the worker

    monkeypatch.setattr(worker, "run_once", fake_run_once)

    await asyncio.wait_for(worker.run_worker(stop, interval_seconds=0.01), timeout=2)

    assert calls == 3


# --- Cron endpoint ---------------------------------------------------------------


async def test_jobs_endpoint_disabled_without_token(client: AsyncClient) -> None:
    response = await client.post("/internal/jobs/run", headers={"X-Jobs-Token": "anything"})

    assert response.status_code == 404


async def test_jobs_endpoint_requires_correct_token(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "jobs_token", SecretStr("s3cret-token"))
    business = await create_business(db_session)
    await create_order(db_session, business, deliver_by=datetime.now(UTC) - timedelta(minutes=1))
    await db_session.commit()

    missing = await client.post("/internal/jobs/run")
    wrong = await client.post("/internal/jobs/run", headers={"X-Jobs-Token": "guess"})
    right = await client.post("/internal/jobs/run", headers={"X-Jobs-Token": "s3cret-token"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert right.status_code == 200
    assert right.json() == {
        "expired_assignments": 0,
        "reassigned": 0,
        "dispatched_pending": 0,
        "flagged_overdue": 1,
    }


def test_jobs_endpoint_is_hidden_from_api_docs() -> None:
    from app.main import app

    assert not any(path.startswith("/internal") for path in app.openapi()["paths"])
