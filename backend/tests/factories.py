"""Small helpers that insert valid domain objects for tests."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Driver, Order, User
from app.models.enums import (
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
