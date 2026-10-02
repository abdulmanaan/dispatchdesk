"""Realistic demo data around Lahore.

All names and businesses are fictional. Coordinates are approximate area centres.
The data is internally consistent: every order has a matching assignment history
and audit timeline, and every busy driver holds exactly one active order.
"""

import random
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.base import Base
from app.demo.accounts import DEMO_EMAILS, SIMULATED_DOMAIN
from app.models import AuditLog, Business, Driver, Order, OrderAssignment, User
from app.models.enums import (
    AssignmentStatus,
    BusinessCategory,
    DriverStatus,
    OrderStatus,
    UserRole,
    VehicleType,
)
from app.services.geo import haversine_km

Stage = Literal["pending", "assigned", "accepted", "picked_up", "delivered", "failed"]


@dataclass(frozen=True)
class Place:
    address: str
    lat: float
    lng: float


BUSINESSES = [
    # (owner, email, name, category, phone, place)
    ("Hamza Butt", DEMO_EMAILS[UserRole.BUSINESS], "Lahori Biryani Corner",
     BusinessCategory.RESTAURANT, "+924235761200",
     Place("21 MM Alam Road, Gulberg III", 31.5145, 74.3510)),
    ("Sana Iqbal", f"liberty@{SIMULATED_DOMAIN}", "Liberty Care Pharmacy",
     BusinessCategory.PHARMACY, "+924235714455",
     Place("Shop 4, Liberty Market, Gulberg", 31.5104, 74.3416)),
    ("Imran Sheikh", f"freshmart@{SIMULATED_DOMAIN}", "Model Town Fresh Mart",
     BusinessCategory.GROCERY, "+924235166030",
     Place("82 Link Road, Model Town", 31.4835, 74.3258)),
    ("Mehwish Akram", f"bakehouse@{SIMULATED_DOMAIN}", "Johar Town Bakehouse",
     BusinessCategory.RESTAURANT, "+924235302218",
     Place("G-1 Market, Johar Town", 31.4697, 74.2728)),
]  # fmt: skip

# The first driver is the demo account (operated by visitors, never simulated).
DRIVERS = [
    ("Kamran Ali", DEMO_EMAILS[UserRole.DRIVER], VehicleType.MOTORBIKE, "+923214567890",
     31.5180, 74.3460, DriverStatus.AVAILABLE),
    ("Usman Tariq", f"usman@{SIMULATED_DOMAIN}", VehicleType.MOTORBIKE, "+923001234501",
     31.5090, 74.3400, DriverStatus.AVAILABLE),
    ("Bilal Ahmed", f"bilal@{SIMULATED_DOMAIN}", VehicleType.MOTORBIKE, "+923001234502",
     31.4860, 74.3290, DriverStatus.AVAILABLE),
    ("Zeeshan Haider", f"zeeshan@{SIMULATED_DOMAIN}", VehicleType.CAR, "+923001234503",
     31.4720, 74.2760, DriverStatus.AVAILABLE),
    ("Asad Mehmood", f"asad@{SIMULATED_DOMAIN}", VehicleType.MOTORBIKE, "+923001234504",
     31.5010, 74.3230, DriverStatus.AVAILABLE),
    ("Faisal Rauf", f"faisal@{SIMULATED_DOMAIN}", VehicleType.BICYCLE, "+923001234505",
     31.5160, 74.3530, DriverStatus.AVAILABLE),
    ("Naveed Akhtar", f"naveed@{SIMULATED_DOMAIN}", VehicleType.MOTORBIKE, "+923001234506",
     31.5130, 74.3880, DriverStatus.AVAILABLE),
    ("Waqas Javed", f"waqas@{SIMULATED_DOMAIN}", VehicleType.CAR, "+923001234507",
     31.4750, 74.4050, DriverStatus.OFFLINE),
    ("Hassan Raza", f"hassan@{SIMULATED_DOMAIN}", VehicleType.MOTORBIKE, "+923001234508",
     31.4480, 74.3080, DriverStatus.OFFLINE),
]  # fmt: skip

DROPOFFS = [
    Place("House 12, Street 5, Model Town", 31.4840, 74.3220),
    Place("Flat 3B, Gulberg Heights, Gulberg II", 31.5230, 74.3480),
    Place("45-C, DHA Phase 5", 31.4650, 74.4090),
    Place("House 7, Block H, Johar Town", 31.4710, 74.2810),
    Place("23 Shadman Market Road, Shadman", 31.5390, 74.3290),
    Place("House 102, Block C, Faisal Town", 31.4790, 74.3030),
    Place("Office 6, Kalma Chowk Plaza, Garden Town", 31.5040, 74.3310),
    Place("House 18, Street 2, Cantt", 31.5180, 74.3920),
    Place("88-E, Iqbal Town", 31.5106, 74.2860),
    Place("House 31, Sector B, Township", 31.4475, 74.3070),
    Place("Apartment 9, Main Boulevard, Gulberg III", 31.5165, 74.3480),
    Place("House 5, Wapda Town Phase 1", 31.4380, 74.2650),
]

CUSTOMERS = [
    ("Ayesha Khan", "+923331112201"), ("Hina Malik", "+923451234567"),
    ("Saad Qureshi", "+923211110203"), ("Fatima Noor", "+923001112233"),
    ("Ahmed Raza", "+923331234567"), ("Zainab Shah", "+923124445566"),
    ("Omar Farooq", "+923216667788"), ("Maryam Aslam", "+923009998877"),
    ("Danish Iqbal", "+923335556677"), ("Rabia Anwar", "+923454443322"),
    ("Hassan Javed", "+923017776655"), ("Noor Fatima", "+923228889900"),
]  # fmt: skip

NOTES = [None, None, "Call on arrival", "Leave with the guard", "Ring the bell twice", None]


@dataclass
class SeedSummary:
    users: int = 0
    orders: int = 0
    skipped: bool = False
    by_stage: dict[str, int] = field(default_factory=dict)


class _Builder:
    """Creates orders in a given lifecycle stage with matching history rows."""

    def __init__(self, session: AsyncSession, rng: random.Random, now: datetime) -> None:
        self.session = session
        self.rng = rng
        self.now = now

    def audit(self, at: datetime, action: str, order: Order, actor: User | None, **details):
        self.session.add(
            AuditLog(
                actor_id=actor.id if actor else None,
                action=action,
                entity_type="order",
                entity_id=str(order.id),
                details=details,
                created_at=at,
            )
        )

    async def order(
        self,
        stage: Stage,
        business: Business,
        owner: User,
        created_at: datetime,
        driver: tuple[Driver, User] | None = None,
        *,
        late: bool = False,
        fail_reason: str = "Customer not answering the phone",
    ) -> Order:
        rng = self.rng
        drop = rng.choice(DROPOFFS)
        name, phone = rng.choice(CUSTOMERS)
        window = timedelta(minutes=rng.choice([45, 60, 60, 75, 90]))
        order = Order(
            business_id=business.id,
            customer_name=name,
            customer_phone=phone,
            pickup_address=business.address,
            pickup_lat=business.lat,
            pickup_lng=business.lng,
            dropoff_address=drop.address,
            dropoff_lat=drop.lat,
            dropoff_lng=drop.lng,
            notes=rng.choice(NOTES),
            deliver_by=created_at + window,
            status=OrderStatus.PENDING,
            assignment_attempts=0,
            created_at=created_at,
            updated_at=created_at,
        )
        self.session.add(order)
        await self.session.flush()
        self.audit(
            created_at, "order.created", order, owner, deliver_by=order.deliver_by.isoformat()
        )

        if stage == "pending" or driver is None:
            if stage == "failed":  # cancelled before any driver took it
                order.status = OrderStatus.FAILED
                order.failed_at = created_at + timedelta(minutes=rng.randint(5, 15))
                order.failure_reason = "Cancelled by business: Customer cancelled"
                self.audit(
                    order.failed_at,
                    "order.cancelled",
                    order,
                    owner,
                    from_status="pending",
                    reason="Customer cancelled",
                )
            return order

        drv, drv_user = driver
        distance = haversine_km(drv.current_lat, drv.current_lng, business.lat, business.lng)
        assigned_at = created_at + timedelta(seconds=rng.randint(20, 120))
        order.status = OrderStatus.ASSIGNED
        order.driver_id = drv.id
        order.assigned_at = assigned_at
        order.assignment_attempts = 1
        assignment = OrderAssignment(order_id=order.id, driver_id=drv.id, assigned_at=assigned_at)
        self.session.add(assignment)
        self.audit(
            assigned_at,
            "order.assigned",
            order,
            None,
            driver_id=str(drv.id),
            distance_km=round(distance, 3),
            candidates=rng.randint(2, 5),
            attempt=1,
        )
        if stage == "assigned":
            return order

        accepted_at = assigned_at + timedelta(seconds=rng.randint(15, 90))
        order.accepted_at = accepted_at
        assignment.status = AssignmentStatus.ACCEPTED
        assignment.accepted_at = accepted_at
        self.audit(accepted_at, "order.accepted", order, drv_user)
        if stage == "accepted":
            return order

        picked_at = accepted_at + timedelta(minutes=rng.randint(6, 14))
        order.status = OrderStatus.PICKED_UP
        order.picked_up_at = picked_at
        self.audit(picked_at, "order.picked_up", order, drv_user)
        if stage == "picked_up":
            return order

        if stage == "failed":
            failed_at = picked_at + timedelta(minutes=rng.randint(10, 25))
            order.status = OrderStatus.FAILED
            order.failed_at = failed_at
            order.failure_reason = f"Failed by driver: {fail_reason}"
            assignment.status = AssignmentStatus.FAILED
            assignment.ended_at = failed_at
            self.audit(
                failed_at,
                "order.failed",
                order,
                drv_user,
                from_status="picked_up",
                reason=fail_reason,
            )
            return order

        trip = rng.randint(10, 22)
        delivered_at = picked_at + timedelta(minutes=trip)
        if late:
            delivered_at = order.deliver_by + timedelta(minutes=rng.randint(4, 15))
        else:
            delivered_at = min(delivered_at, order.deliver_by - timedelta(minutes=2))
        order.status = OrderStatus.DELIVERED
        order.delivered_at = delivered_at
        assignment.status = AssignmentStatus.COMPLETED
        assignment.ended_at = delivered_at
        self.audit(
            delivered_at, "order.delivered", order, drv_user, late=delivered_at > order.deliver_by
        )
        return order


async def _reset(session: AsyncSession) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


async def seed_demo(
    session: AsyncSession, *, reset: bool = False, now: datetime | None = None, seed: int = 7
) -> SeedSummary:
    """Create the demo data set. Without ``reset`` an existing demo is left alone."""
    summary = SeedSummary()
    already = await session.scalar(select(User.id).where(User.email == DEMO_EMAILS[UserRole.ADMIN]))
    if already and not reset:
        summary.skipped = True
        return summary
    if reset:
        await _reset(session)

    now = now or datetime.now(UTC)
    rng = random.Random(seed)
    # Nobody needs these passwords: demo visitors use the one-click demo login.
    password_hash = hash_password(secrets.token_urlsafe(24))

    def new_user(name: str, email: str, role: UserRole) -> User:
        user = User(email=email, full_name=name, role=role, hashed_password=password_hash)
        session.add(user)
        summary.users += 1
        return user

    new_user("Ayesha Siddiqui", DEMO_EMAILS[UserRole.ADMIN], UserRole.ADMIN)

    businesses: list[tuple[Business, User]] = []
    for owner_name, email, name, category, phone, place in BUSINESSES:
        owner = new_user(owner_name, email, UserRole.BUSINESS)
        owner.business = Business(
            name=name,
            category=category,
            phone=phone,
            address=place.address,
            lat=place.lat,
            lng=place.lng,
        )
        businesses.append((owner.business, owner))

    drivers: list[tuple[Driver, User]] = []
    for name, email, vehicle, phone, lat, lng, status in DRIVERS:
        user = new_user(name, email, UserRole.DRIVER)
        user.driver = Driver(
            phone=phone,
            vehicle_type=vehicle,
            status=status,
            current_lat=lat,
            current_lng=lng,
            location_updated_at=now,
        )
        drivers.append((user.driver, user))
    await session.flush()

    build = _Builder(session, rng, now)
    stages: list[str] = []

    # History: the last 24 hours of finished orders.
    for i in range(22):
        business, owner = rng.choice(businesses)
        created = now - timedelta(hours=23) + timedelta(minutes=i * 60 + rng.randint(0, 30))
        stage: Stage = "failed" if i in (5, 14) else "delivered"
        driver = rng.choice(drivers[:7])  # drivers that are on shift today
        cancelled_early = i == 14
        await build.order(
            stage,
            business,
            owner,
            created,
            None if cancelled_early else driver,
            late=i in (3, 11, 17),
        )
        stages.append(stage)

    # Live orders, one per driver at most (enforced by the unique index anyway).
    demo_business, demo_owner = businesses[0]
    kamran, usman, bilal, zeeshan = drivers[0], drivers[1], drivers[2], drivers[3]
    live = [
        # The demo driver is heading to the demo restaurant, ready to pick up.
        ("accepted", demo_business, demo_owner, kamran, now - timedelta(minutes=6), False),
        ("picked_up", businesses[1][0], businesses[1][1], usman, now - timedelta(minutes=48), True),
        ("assigned", businesses[2][0], businesses[2][1], bilal, now - timedelta(minutes=1), False),
        (
            "accepted",
            businesses[3][0],
            businesses[3][1],
            zeeshan,
            now - timedelta(minutes=9),
            False,
        ),
        ("pending", demo_business, demo_owner, None, now - timedelta(minutes=2), False),
    ]
    for stage, business, owner, driver, created, overdue in live:
        order = await build.order(stage, business, owner, created, driver)  # type: ignore[arg-type]
        if overdue:
            # Created long enough ago that the deadline has passed.
            order.deliver_by = now - timedelta(minutes=5)
            order.is_overdue = True
            build.audit(order.deliver_by + timedelta(minutes=1), "order.overdue", order, None)
        if driver is not None:
            driver[0].status = DriverStatus.BUSY
        stages.append(stage)

    await session.commit()
    summary.orders = len(stages)
    summary.by_stage = {s: stages.count(s) for s in sorted(set(stages))}
    return summary
