"""Order use cases: create, list, fetch and cancel.

Locking rule (to avoid deadlocks): when both are needed, always lock the
order row first, then the driver row.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.models import Driver, Order, OrderAssignment, User
from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
    OPEN_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    DriverStatus,
    OrderStatus,
    UserRole,
)
from app.schemas.order import OrderCreate, OrderListParams
from app.services import audit, order_state

_SORT_COLUMNS = {
    "created_at": Order.created_at.asc(),
    "-created_at": Order.created_at.desc(),
    "deliver_by": Order.deliver_by.asc(),
    "-deliver_by": Order.deliver_by.desc(),
}


def _visibility_filter(user: User) -> ColumnElement[bool] | None:
    """Rows the user may see: admins all, businesses their own, drivers their assigned."""
    if user.role == UserRole.ADMIN:
        return None
    if user.role == UserRole.BUSINESS:
        assert user.business is not None
        return Order.business_id == user.business.id
    assert user.driver is not None
    return Order.driver_id == user.driver.id


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _list_conditions(user: User, params: OrderListParams) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if (visible := _visibility_filter(user)) is not None:
        conditions.append(visible)
    if params.status:
        conditions.append(Order.status.in_(params.status))
    if params.business_id:
        conditions.append(Order.business_id == params.business_id)
    if params.driver_id:
        conditions.append(Order.driver_id == params.driver_id)
    if params.is_overdue is not None:
        conditions.append(Order.is_overdue.is_(params.is_overdue))
    if params.created_from:
        conditions.append(Order.created_at >= params.created_from)
    if params.created_to:
        conditions.append(Order.created_at < params.created_to)
    if params.search:
        pattern = f"%{_escape_like(params.search)}%"
        conditions.append(
            or_(
                Order.customer_name.ilike(pattern, escape="\\"),
                Order.customer_phone.ilike(pattern, escape="\\"),
                Order.dropoff_address.ilike(pattern, escape="\\"),
            )
        )
    return conditions


async def list_orders(
    session: AsyncSession, user: User, params: OrderListParams
) -> tuple[Sequence[Order], int]:
    """Return one page of orders visible to ``user`` plus the total match count."""
    conditions = _list_conditions(user, params)

    total = await session.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
    stmt = (
        select(Order)
        .where(*conditions)
        # id as a tie-breaker keeps pagination stable when timestamps are equal.
        .order_by(_SORT_COLUMNS[params.sort], Order.id)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    items = (await session.scalars(stmt)).all()
    return items, total


def _visible_order_query(user: User, order_id: uuid.UUID) -> Select[tuple[Order]]:
    stmt = select(Order).where(Order.id == order_id)
    if (visible := _visibility_filter(user)) is not None:
        stmt = stmt.where(visible)
    return stmt


async def get_order(
    session: AsyncSession, user: User, order_id: uuid.UUID, *, for_update: bool = False
) -> Order:
    """Fetch an order the user may see. Invisible orders are reported as not found."""
    stmt = _visible_order_query(user, order_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    order = await session.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def create_order(session: AsyncSession, user: User, data: OrderCreate) -> Order:
    business = user.business
    assert business is not None
    now = datetime.now(UTC)
    deliver_by = data.deliver_by or now + timedelta(
        minutes=get_settings().default_delivery_window_minutes
    )

    order = Order(
        business_id=business.id,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        pickup_address=data.pickup_address or business.address,
        pickup_lat=data.pickup_lat if data.pickup_lat is not None else business.lat,
        pickup_lng=data.pickup_lng if data.pickup_lng is not None else business.lng,
        dropoff_address=data.dropoff_address,
        dropoff_lat=data.dropoff_lat,
        dropoff_lng=data.dropoff_lng,
        notes=data.notes,
        deliver_by=deliver_by,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.flush()
    audit.record(
        session,
        actor=user,
        action="order.created",
        entity_type="order",
        entity_id=order.id,
        details={"deliver_by": deliver_by.isoformat()},
    )
    await session.commit()
    return order


async def release_driver(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    driver_id: uuid.UUID,
    outcome: AssignmentStatus,
    now: datetime,
) -> None:
    """Close the order's open assignment and make a busy driver available again.

    Call only while holding the order's row lock (see the locking rule above).
    """
    await session.execute(
        update(OrderAssignment)
        .where(
            OrderAssignment.order_id == order_id,
            OrderAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
        )
        .values(status=outcome, ended_at=now)
    )
    driver = await session.get(Driver, driver_id, with_for_update=True, populate_existing=True)
    if driver is not None and driver.status == DriverStatus.BUSY:
        driver.status = DriverStatus.AVAILABLE


async def cancel_order(
    session: AsyncSession, user: User, order_id: uuid.UUID, reason: str | None
) -> Order:
    """Cancel an open order (recorded as ``failed`` with a cancellation reason).

    Businesses may cancel only before pickup; admins may cancel any open order.
    """
    order = await get_order(session, user, order_id, for_update=True)

    if user.role == UserRole.BUSINESS and order.status == OrderStatus.PICKED_UP:
        raise ConflictError("Order has already been picked up and can no longer be cancelled")

    previous_status = order.status
    driver_id = order.driver_id
    now = datetime.now(UTC)
    failure_reason = f"Cancelled by {user.role.value}" + (f": {reason}" if reason else "")

    order_state.fail(order, reason=failure_reason, now=now)
    if previous_status in ACTIVE_ORDER_STATUSES and driver_id is not None:
        await release_driver(
            session,
            order_id=order.id,
            driver_id=driver_id,
            outcome=AssignmentStatus.FAILED,
            now=now,
        )

    audit.record(
        session,
        actor=user,
        action="order.cancelled",
        entity_type="order",
        entity_id=order.id,
        details={"from_status": previous_status.value, "reason": reason},
    )
    await session.commit()
    return order
