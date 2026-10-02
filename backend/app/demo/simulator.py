"""Background drivers for the public demo.

In demo mode, seeded "simulated" drivers (see ``accounts.SIMULATED_DOMAIN``)
behave like real riders on a timer: they accept offers, pick up and deliver.
This keeps the live demo moving when a visitor creates an order that goes to
one of them. The demo driver account that visitors use is never automated.

All steps go through the normal order services, so locking, assignment history
and audit entries are exactly the same as for a human driver.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.demo.accounts import SIMULATED_DOMAIN
from app.models import Driver, Order, User
from app.models.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from app.services import orders as order_service
from app.services.auth import get_user_with_profiles

logger = logging.getLogger(__name__)

ACCEPT_AFTER = timedelta(seconds=20)
PICK_UP_AFTER = timedelta(seconds=45)
DELIVER_AFTER = timedelta(seconds=90)


def _next_step(order: Order, now: datetime):
    """The service call that moves this order on, if its wait time has passed."""
    if order.status == OrderStatus.PICKED_UP:
        ready = order.picked_up_at is not None and now - order.picked_up_at >= DELIVER_AFTER
        return order_service.deliver_order if ready else None
    if order.status != OrderStatus.ASSIGNED:
        return None
    if order.accepted_at is None:
        ready = order.assigned_at is not None and now - order.assigned_at >= ACCEPT_AFTER
        return order_service.accept_order if ready else None
    return order_service.pick_up_order if now - order.accepted_at >= PICK_UP_AFTER else None


async def advance_simulated_drivers(session: AsyncSession) -> int:
    """Move each simulated driver's active order one step forward. Returns steps taken."""
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(Order, User.id)
            .join(Driver, Driver.id == Order.driver_id)
            .join(User, User.id == Driver.user_id)
            .where(
                Order.status.in_(ACTIVE_ORDER_STATUSES),
                User.email.endswith(f"@{SIMULATED_DOMAIN}"),
            )
        )
    ).all()
    planned: list[tuple[uuid.UUID, uuid.UUID, object]] = [
        (order.id, user_id, step) for order, user_id in rows if (step := _next_step(order, now))
    ]
    await session.commit()

    steps = 0
    for order_id, user_id, step in planned:
        user = await get_user_with_profiles(session, user_id)
        if user is None:
            continue
        try:
            await step(session, user, order_id)  # type: ignore[operator]
            steps += 1
        except DomainError as exc:
            # The order changed in between (e.g. cancelled); nothing to do.
            await session.rollback()
            logger.info("Simulated step skipped for order %s: %s", order_id, exc.detail)
    return steps
