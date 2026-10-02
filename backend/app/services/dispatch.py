"""Auto-dispatch: assign a pending order to the best available driver.

Selection
    Candidates are drivers that are ``available``, have a recent location within
    ``dispatch_max_radius_km`` of the pickup point, and have not already let this
    order expire. Each gets a score (lower is better)::

        score = distance_to_pickup_km + recent_deliveries * workload_penalty_km

    so the nearest driver usually wins, but work is spread fairly among drivers
    at similar distances.

Concurrency
    Everything happens in one transaction:

    1. Lock the order row (``FOR UPDATE SKIP LOCKED``) and re-check it is pending.
       A concurrent dispatch or cancel of the same order makes us skip it.
    2. Read candidate drivers *without* locking and rank them.
    3. Walk the ranking and lock only the chosen driver (``FOR UPDATE SKIP LOCKED``,
       re-checking ``status = available`` under the lock). If another transaction
       holds or just took that driver, move on to the next candidate. Locking one
       driver (not all candidates) lets parallel dispatches use different drivers.
    4. Assign, mark the driver ``busy`` and commit.

    Locks are taken order first, then the driver, matching the rest of the code base.
    The partial unique index ``uq_orders_driver_active`` remains as a final guard.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Driver, Order, OrderAssignment, User
from app.models.enums import AssignmentStatus, DriverStatus, OrderStatus
from app.services import audit, order_state
from app.services.geo import bounding_box, haversine_km

logger = logging.getLogger(__name__)


class DispatchOutcome(StrEnum):
    ASSIGNED = "assigned"
    NO_DRIVER = "no_driver"  # nobody suitable right now; the order stays pending
    NOT_PENDING = "not_pending"  # already assigned, delivered, cancelled...
    LOCKED = "locked"  # another transaction is working on this order
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"  # lost a race caught by the unique index (should not happen)


@dataclass(frozen=True)
class DispatchResult:
    order_id: uuid.UUID
    outcome: DispatchOutcome
    driver_id: uuid.UUID | None = None
    distance_km: float | None = None
    candidates: int = 0


@dataclass(frozen=True)
class Candidate:
    driver_id: uuid.UUID
    distance_km: float
    recent_deliveries: int


def score(candidate: Candidate, workload_penalty_km: float) -> float:
    return candidate.distance_km + candidate.recent_deliveries * workload_penalty_km


def rank_candidates(candidates: Sequence[Candidate], workload_penalty_km: float) -> list[Candidate]:
    """Best candidate first. Ties go to the nearer driver, then a stable id order."""
    return sorted(
        candidates,
        key=lambda c: (score(c, workload_penalty_km), c.distance_km, str(c.driver_id)),
    )


async def _lock_order(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )


async def _find_candidate_drivers(
    session: AsyncSession, order: Order, now: datetime, settings: Settings
) -> list[Driver]:
    """Available drivers near the pickup (unlocked read; re-checked when locking)."""
    box = bounding_box(order.pickup_lat, order.pickup_lng, settings.dispatch_max_radius_km)
    expired_on_this_order = select(OrderAssignment.driver_id).where(
        OrderAssignment.order_id == order.id,
        OrderAssignment.status == AssignmentStatus.EXPIRED,
    )
    stmt = select(Driver).where(
        Driver.status == DriverStatus.AVAILABLE,
        Driver.current_lat.between(box.min_lat, box.max_lat),
        Driver.current_lng.between(box.min_lng, box.max_lng),
        Driver.id.not_in(expired_on_this_order),
    )
    if settings.dispatch_location_max_age_minutes > 0:
        cutoff = now - timedelta(minutes=settings.dispatch_location_max_age_minutes)
        stmt = stmt.where(Driver.location_updated_at >= cutoff)
    return list((await session.scalars(stmt)).all())


async def _lock_if_still_available(session: AsyncSession, driver_id: uuid.UUID) -> Driver | None:
    """Lock the driver row unless another transaction holds it; None if taken."""
    return await session.scalar(
        select(Driver)
        .where(Driver.id == driver_id, Driver.status == DriverStatus.AVAILABLE)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )


async def _recent_deliveries(
    session: AsyncSession, driver_ids: Sequence[uuid.UUID], since: datetime
) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(OrderAssignment.driver_id, func.count())
        .where(
            OrderAssignment.driver_id.in_(driver_ids),
            OrderAssignment.status == AssignmentStatus.COMPLETED,
            OrderAssignment.ended_at >= since,
        )
        .group_by(OrderAssignment.driver_id)
    )
    return {driver_id: count for driver_id, count in rows.all()}


async def try_dispatch_order(
    session: AsyncSession, order_id: uuid.UUID, *, actor: User | None = None
) -> DispatchResult:
    """Try to assign one order. Always ends the transaction (commit or rollback).

    ``actor`` is recorded in the audit log; ``None`` means automatic dispatch.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    order = await _lock_order(session, order_id)
    if order is None:
        await session.commit()
        exists = await session.scalar(select(Order.id).where(Order.id == order_id))
        outcome = DispatchOutcome.LOCKED if exists else DispatchOutcome.NOT_FOUND
        return DispatchResult(order_id, outcome)
    if order.status != OrderStatus.PENDING:
        await session.commit()
        return DispatchResult(order_id, DispatchOutcome.NOT_PENDING)

    drivers = await _find_candidate_drivers(session, order, now, settings)
    in_range = {
        d.id: haversine_km(d.current_lat, d.current_lng, order.pickup_lat, order.pickup_lng)
        for d in drivers
        if d.current_lat is not None and d.current_lng is not None
    }
    in_range = {k: v for k, v in in_range.items() if v <= settings.dispatch_max_radius_km}

    since = now - timedelta(hours=settings.dispatch_workload_window_hours)
    workload = await _recent_deliveries(session, list(in_range), since) if in_range else {}
    candidates = [Candidate(d, dist, workload.get(d, 0)) for d, dist in in_range.items()]

    driver: Driver | None = None
    for best in rank_candidates(candidates, settings.dispatch_workload_penalty_km):
        driver = await _lock_if_still_available(session, best.driver_id)
        if driver is not None:
            break
    if driver is None:
        await session.commit()  # releases the order lock; nothing changed
        return DispatchResult(order_id, DispatchOutcome.NO_DRIVER, candidates=len(candidates))

    order_state.assign(order, driver.id, now=now)
    session.add(OrderAssignment(order_id=order.id, driver_id=driver.id, assigned_at=now))
    driver.status = DriverStatus.BUSY
    audit.record(
        session,
        actor=actor,
        action="order.assigned",
        entity_type="order",
        entity_id=order.id,
        details={
            "driver_id": str(driver.id),
            "distance_km": round(best.distance_km, 3),
            "recent_deliveries": best.recent_deliveries,
            "score": round(score(best, settings.dispatch_workload_penalty_km), 3),
            "candidates": len(candidates),
            "attempt": order.assignment_attempts,
        },
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.warning("Dispatch of order %s lost a race on the unique index", order_id)
        return DispatchResult(order_id, DispatchOutcome.CONFLICT)

    logger.info("Order %s assigned to driver %s (%.2f km)", order_id, driver.id, best.distance_km)
    return DispatchResult(
        order_id,
        DispatchOutcome.ASSIGNED,
        driver_id=driver.id,
        distance_km=best.distance_km,
        candidates=len(candidates),
    )


async def dispatch_pending_orders(
    session: AsyncSession, *, limit: int = 20, actor: User | None = None
) -> list[DispatchResult]:
    """Try to assign the most urgent pending orders, one transaction per order."""
    order_ids = (
        await session.scalars(
            select(Order.id)
            .where(Order.status == OrderStatus.PENDING)
            .order_by(Order.deliver_by, Order.created_at)
            .limit(limit)
        )
    ).all()
    await session.commit()  # end the read transaction before per-order work

    results = []
    for order_id in order_ids:
        results.append(await try_dispatch_order(session, order_id, actor=actor))
    return results


async def dispatch_quietly(session: AsyncSession, order_id: uuid.UUID | None = None) -> None:
    """Best-effort dispatch after another action has already been committed.

    Failures are logged, never raised: the caller's action already succeeded and
    pending orders are retried by the background job anyway.
    """
    try:
        if order_id is None:
            await dispatch_pending_orders(session)
        else:
            await try_dispatch_order(session, order_id)
    except Exception:
        logger.exception("Automatic dispatch failed")
        await session.rollback()
