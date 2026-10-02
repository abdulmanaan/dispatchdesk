"""Database-level guarantees: migrations and constraints.

These tests insert rows directly (bypassing services) to prove the database
itself rejects invalid states, independent of application logic.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.models import OrderAssignment
from app.models.enums import AssignmentStatus, OrderStatus
from tests.conftest import alembic_config
from tests.factories import (
    active_order_fields,
    create_business,
    create_driver,
    create_order,
)


async def test_migrations_match_models() -> None:
    """Fails if a model was changed without generating a migration."""
    await asyncio.to_thread(command.check, alembic_config())


async def assert_violates(session: AsyncSession, constraint: str) -> None:
    """Flush pending changes and assert the named constraint rejects them."""
    with pytest.raises(IntegrityError) as exc_info:
        await session.flush()
    assert constraint in str(exc_info.value)
    await session.rollback()


# --- One active order per driver -------------------------------------------------


@pytest.mark.parametrize("second_status", [OrderStatus.ASSIGNED, OrderStatus.PICKED_UP])
async def test_driver_cannot_hold_two_active_orders(
    db_session: AsyncSession, second_status: OrderStatus
) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    await create_order(db_session, business, **active_order_fields(driver))

    with pytest.raises(IntegrityError) as exc_info:
        await create_order(db_session, business, **active_order_fields(driver, second_status))
    assert "uq_orders_driver_active" in str(exc_info.value)


async def test_driver_can_take_new_order_after_delivery(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    await create_order(db_session, business, **active_order_fields(driver, OrderStatus.DELIVERED))
    await create_order(db_session, business, **active_order_fields(driver, OrderStatus.FAILED))

    # Finished orders do not count, so a new active order is allowed.
    await create_order(db_session, business, **active_order_fields(driver))


async def test_different_drivers_can_hold_active_orders(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    first, second = await create_driver(db_session), await create_driver(db_session)

    await create_order(db_session, business, **active_order_fields(first))
    await create_order(db_session, business, **active_order_fields(second))


# --- Order status consistency ----------------------------------------------------


async def test_pending_order_cannot_have_driver(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    order = await create_order(db_session, business)

    order.driver_id = driver.id
    await assert_violates(db_session, "ck_orders_driver_matches_status")


@pytest.mark.parametrize(
    "status", [OrderStatus.ASSIGNED, OrderStatus.PICKED_UP, OrderStatus.DELIVERED]
)
async def test_active_or_delivered_order_requires_driver(
    db_session: AsyncSession, status: OrderStatus
) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)

    order.status = status
    # Set accepted_at so the only rule broken is the missing driver.
    order.accepted_at = datetime.now(UTC)
    await assert_violates(db_session, "ck_orders_driver_matches_status")


async def test_pickup_requires_acceptance(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    order = await create_order(db_session, business, **active_order_fields(driver))

    order.status = OrderStatus.PICKED_UP  # accepted_at is still NULL
    await assert_violates(db_session, "ck_orders_accepted_before_pickup")


async def test_order_rejects_invalid_coordinates(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)

    order.dropoff_lat = 95.0
    await assert_violates(db_session, "ck_orders_valid_dropoff")


async def test_unknown_enum_value_is_rejected_by_database(db_session: AsyncSession) -> None:
    driver = await create_driver(db_session)
    await db_session.commit()

    # Raw SQL bypasses Python-side enum validation, so only the CHECK can stop it.
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text("UPDATE drivers SET vehicle_type = 'rocket' WHERE id = :id"), {"id": driver.id}
        )
    assert "ck_drivers_vehicle_type" in str(exc_info.value)


# --- Drivers and assignments -----------------------------------------------------


async def test_driver_location_must_be_complete(db_session: AsyncSession) -> None:
    driver = await create_driver(db_session)

    driver.current_lng = None
    await assert_violates(db_session, "ck_drivers_location_both_or_neither")


async def test_order_has_at_most_one_open_assignment(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    first, second = await create_driver(db_session), await create_driver(db_session)
    order = await create_order(db_session, business)

    db_session.add(
        OrderAssignment(order_id=order.id, driver_id=first.id, status=AssignmentStatus.EXPIRED)
    )
    db_session.add(OrderAssignment(order_id=order.id, driver_id=second.id))
    await db_session.flush()  # one expired + one open is fine

    db_session.add(OrderAssignment(order_id=order.id, driver_id=first.id))
    await assert_violates(db_session, "uq_order_assignments_order_open")
