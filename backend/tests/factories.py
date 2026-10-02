"""Small helpers that insert valid domain objects for tests."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import Business, Driver, Order, OrderAssignment, User
from app.models.enums import (
    AssignmentStatus,
    BusinessCategory,
    DriverStatus,
    OrderStatus,
    UserRole,
    VehicleType,
)

# Liberty Market, Lahore: a convenient default coordinate.
LAHORE_LAT, LAHORE_LNG = 31.5104, 74.3416


async def create_user(session: AsyncSession, role: UserRole, **overrides: Any) -> User:
    user = User(
        email=f"{role.value}-{uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        full_name="Test User",
        role=role,
        **overrides,
    )
    session.add(user)
    await session.flush()
    return user


async def create_business(session: AsyncSession, **overrides: Any) -> Business:
    owner = await create_user(session, UserRole.BUSINESS)
    business = Business(
        owner_id=owner.id,
        name="Test Biryani House",
        category=BusinessCategory.RESTAURANT,
        phone="+923001234567",
        address="Main Market, Gulberg, Lahore",
        lat=LAHORE_LAT,
        lng=LAHORE_LNG,
        **overrides,
    )
    session.add(business)
    await session.flush()
    return business


async def create_driver(session: AsyncSession, **overrides: Any) -> Driver:
    user = await create_user(session, UserRole.DRIVER)
    values: dict[str, Any] = {
        "phone": "+923007654321",
        "vehicle_type": VehicleType.MOTORBIKE,
        "status": DriverStatus.AVAILABLE,
        "current_lat": LAHORE_LAT,
        "current_lng": LAHORE_LNG,
    } | overrides
    driver = Driver(user_id=user.id, **values)
    session.add(driver)
    await session.flush()
    return driver


async def create_order(session: AsyncSession, business: Business, **overrides: Any) -> Order:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "customer_name": "Ayesha Khan",
        "customer_phone": "+923331112233",
        "pickup_address": business.address,
        "pickup_lat": business.lat,
        "pickup_lng": business.lng,
        "dropoff_address": "Block H, DHA Phase 5, Lahore",
        "dropoff_lat": 31.4697,
        "dropoff_lng": 74.4110,
        "deliver_by": now + timedelta(minutes=45),
        "status": OrderStatus.PENDING,
    } | overrides
    order = Order(business_id=business.id, **values)
    session.add(order)
    await session.flush()
    return order


def active_order_fields(driver: Driver, status: OrderStatus = OrderStatus.ASSIGNED) -> dict:
    """Field overrides for an order currently held by ``driver``."""
    now = datetime.now(UTC)
    fields: dict[str, Any] = {"driver_id": driver.id, "status": status, "assigned_at": now}
    if status != OrderStatus.ASSIGNED:
        fields["accepted_at"] = now
    return fields


def auth_headers(user_id: Any, role: UserRole) -> dict[str, str]:
    """Bearer headers for a user, minted directly (no login round-trip)."""
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


def business_headers(business: Business) -> dict[str, str]:
    return auth_headers(business.owner_id, UserRole.BUSINESS)


def driver_headers(driver: Driver) -> dict[str, str]:
    return auth_headers(driver.user_id, UserRole.DRIVER)


async def assign_order(
    session: AsyncSession, order: Order, driver: Driver, *, accepted: bool = False
) -> None:
    """Put an order into the assigned state the way dispatch will: order, assignment, driver."""
    now = datetime.now(UTC)
    order.status = OrderStatus.ASSIGNED
    order.driver_id = driver.id
    order.assigned_at = now
    order.accepted_at = now if accepted else None
    order.assignment_attempts += 1
    session.add(
        OrderAssignment(
            order_id=order.id,
            driver_id=driver.id,
            status=AssignmentStatus.ACCEPTED if accepted else AssignmentStatus.OFFERED,
            accepted_at=order.accepted_at,
        )
    )
    driver.status = DriverStatus.BUSY
    await session.flush()
