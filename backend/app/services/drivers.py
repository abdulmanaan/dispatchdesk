"""Driver self-service (status, location) and the admin driver list.

Invariant: a driver is ``busy`` exactly when they hold an active order. Only
dispatch sets ``busy``; completing or failing the order sets ``available`` again.
Drivers themselves may only switch between ``available`` and ``offline``.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.db.utils import like_pattern
from app.models import Driver, Order, User
from app.models.enums import ACTIVE_ORDER_STATUSES, DriverStatus
from app.schemas.driver import DriverListParams, DriverStatusUpdate, LocationUpdate
from app.services import audit


async def _lock_own_driver(session: AsyncSession, user: User) -> Driver:
    """Row-lock the caller's driver profile so status changes serialize with dispatch."""
    assert user.driver is not None
    driver = await session.get(Driver, user.driver.id, with_for_update=True, populate_existing=True)
    assert driver is not None
    return driver


def _set_location(driver: Driver, lat: float, lng: float, now: datetime) -> None:
    driver.current_lat = lat
    driver.current_lng = lng
    driver.location_updated_at = now


async def update_location(session: AsyncSession, user: User, data: LocationUpdate) -> Driver:
    driver = await _lock_own_driver(session, user)
    _set_location(driver, data.lat, data.lng, datetime.now(UTC))
    # Location pings are frequent and low-value, so they are not audited.
    await session.commit()
    return driver


async def set_status(session: AsyncSession, user: User, data: DriverStatusUpdate) -> Driver:
    driver = await _lock_own_driver(session, user)
    now = datetime.now(UTC)

    if driver.status == DriverStatus.BUSY:
        raise ConflictError("You have an active order. Deliver or fail it before changing status")
    if data.lat is not None and data.lng is not None:
        _set_location(driver, data.lat, data.lng, now)
    if data.status == DriverStatus.AVAILABLE and driver.current_lat is None:
        raise ConflictError("Share your location before going available")

    previous = driver.status
    driver.status = DriverStatus(data.status)
    if previous != driver.status:
        audit.record(
            session,
            actor=user,
            action="driver.status_changed",
            entity_type="driver",
            entity_id=driver.id,
            details={"from": previous.value, "to": driver.status.value},
        )
    await session.commit()
    return driver


async def list_drivers(
    session: AsyncSession, params: DriverListParams
) -> tuple[Sequence[dict[str, Any]], int]:
    """One page of drivers with their user details and current active order."""
    conditions = []
    if params.status:
        conditions.append(Driver.status.in_(params.status))
    if params.vehicle_type:
        conditions.append(Driver.vehicle_type == params.vehicle_type)
    if params.search:
        pattern = like_pattern(params.search)
        conditions.append(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
                Driver.phone.ilike(pattern, escape="\\"),
            )
        )

    base = select(Driver).join(User, User.id == Driver.user_id).where(*conditions)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0

    stmt = (
        select(Driver, User.full_name, User.email, Order.id.label("active_order_id"))
        .join(User, User.id == Driver.user_id)
        # At most one active order per driver (unique index), so no duplicate rows.
        .outerjoin(
            Order,
            and_(Order.driver_id == Driver.id, Order.status.in_(ACTIVE_ORDER_STATUSES)),
        )
        .where(*conditions)
        .order_by(User.full_name, Driver.id)
        .offset(params.offset)
        .limit(params.page_size)
    )
    rows = (await session.execute(stmt)).all()
    items = [
        {
            **{c.key: getattr(driver, c.key) for c in Driver.__table__.columns},
            "full_name": full_name,
            "email": email,
            "active_order_id": active_order_id,
        }
        for driver, full_name, email, active_order_id in rows
    ]
    return items, total
