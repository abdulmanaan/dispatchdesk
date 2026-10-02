"""Background jobs.

Every job is safe to run concurrently with itself, with API requests and with
another runner (e.g. the local worker and the cron endpoint at the same time):

* per-order work locks the order with ``FOR UPDATE SKIP LOCKED`` and re-checks
  its state under the lock, so each order is handled by exactly one runner;
* bulk flagging is a single atomic ``UPDATE ... RETURNING``.

No global "only one runner" lock is used on purpose: session-level advisory
locks do not survive transaction-mode connection poolers such as Neon's.
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.demo.simulator import advance_simulated_drivers
from app.models import Order
from app.models.enums import OPEN_ORDER_STATUSES, AssignmentStatus, DriverStatus, OrderStatus
from app.services import audit, order_state
from app.services.dispatch import DispatchOutcome, dispatch_pending_orders, try_dispatch_order
from app.services.orders import release_driver

logger = logging.getLogger(__name__)


@dataclass
class JobReport:
    simulated_steps: int = 0  # demo mode only
    expired_assignments: int = 0
    reassigned: int = 0
    dispatched_pending: int = 0
    flagged_overdue: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _unaccepted_and_expired(cutoff: datetime):
    """SQL condition for assigned orders not accepted before ``cutoff``."""
    return (
        Order.status == OrderStatus.ASSIGNED,
        Order.accepted_at.is_(None),
        Order.assigned_at < cutoff,
    )


async def _expire_one(session: AsyncSession, order_id: uuid.UUID, cutoff: datetime) -> bool:
    """Take an unaccepted order back from its driver. False if someone else got there first."""
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id, *_unaccepted_and_expired(cutoff))
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if order is None:  # accepted, cancelled or being handled by another runner
        await session.commit()
        return False

    driver_id = order.driver_id
    assert driver_id is not None
    now = datetime.now(UTC)

    order_state.unassign(order)
    # The driver ignored the offer, so they are probably not watching the app.
    # Taking them offline stops them from timing out on order after order.
    driver = await release_driver(
        session,
        order_id=order.id,
        driver_id=driver_id,
        outcome=AssignmentStatus.EXPIRED,
        now=now,
        driver_status=DriverStatus.OFFLINE,
    )
    audit.record(
        session,
        actor=None,
        action="order.assignment_expired",
        entity_type="order",
        entity_id=order.id,
        details={"driver_id": str(driver_id), "attempt": order.assignment_attempts},
    )
    if driver is not None and driver.status == DriverStatus.OFFLINE:
        audit.record(
            session,
            actor=None,
            action="driver.status_changed",
            entity_type="driver",
            entity_id=driver_id,
            details={"from": "busy", "to": "offline", "reason": "acceptance_timeout"},
        )
    await session.commit()
    return True


async def expire_unaccepted_assignments(session: AsyncSession, report: JobReport) -> None:
    """Reassign orders whose driver did not accept within the timeout."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.acceptance_timeout_seconds)

    order_ids = (
        await session.scalars(
            select(Order.id)
            .where(*_unaccepted_and_expired(cutoff))
            .order_by(Order.assigned_at)
            .limit(settings.jobs_batch_size)
        )
    ).all()
    await session.commit()

    for order_id in order_ids:
        if not await _expire_one(session, order_id, cutoff):
            continue
        report.expired_assignments += 1
        # Offer it to someone else right away (the expired driver is excluded).
        result = await try_dispatch_order(session, order_id)
        if result.outcome == DispatchOutcome.ASSIGNED:
            report.reassigned += 1


async def dispatch_waiting_orders(session: AsyncSession, report: JobReport) -> None:
    """Retry pending orders, e.g. those created while no driver was free."""
    results = await dispatch_pending_orders(session, limit=get_settings().jobs_batch_size)
    report.dispatched_pending += sum(r.outcome == DispatchOutcome.ASSIGNED for r in results)


async def flag_overdue_orders(session: AsyncSession, report: JobReport) -> None:
    """Mark open orders past their deadline as overdue (once)."""
    now = datetime.now(UTC)
    flagged = (
        await session.scalars(
            update(Order)
            .where(
                Order.status.in_(OPEN_ORDER_STATUSES),
                Order.deliver_by < now,
                Order.is_overdue.is_(False),
            )
            .values(is_overdue=True)
            .returning(Order.id)
        )
    ).all()
    for order_id in flagged:
        audit.record(
            session,
            actor=None,
            action="order.overdue",
            entity_type="order",
            entity_id=order_id,
        )
    await session.commit()
    report.flagged_overdue += len(flagged)


async def simulate_demo_drivers(session: AsyncSession, report: JobReport) -> None:
    """Demo mode: let seeded background drivers work their orders."""
    report.simulated_steps += await advance_simulated_drivers(session)


async def run_all_jobs(session: AsyncSession) -> JobReport:
    """Run every job once. Each job is isolated: one failing does not stop the rest."""
    report = JobReport()
    jobs = [expire_unaccepted_assignments, dispatch_waiting_orders, flag_overdue_orders]
    if get_settings().demo_mode:
        # Runs first, so simulated drivers accept before the expiry job looks.
        jobs.insert(0, simulate_demo_drivers)
    for job in jobs:
        try:
            await job(session, report)
        except Exception:
            logger.exception("Job %s failed", job.__name__)
            await session.rollback()
    return report
