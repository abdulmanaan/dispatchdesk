"""Delivery orders and the history of their driver assignments."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
    OPEN_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    OrderStatus,
    enum_column,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, coordinate_checks

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.driver import Driver


def _in_list(column: str, values: tuple[str, ...]) -> str:
    """Render ``column IN ('a', 'b')`` for use in partial indexes and checks."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(coordinate_checks("pickup_lat", "pickup_lng"), name="valid_pickup"),
        CheckConstraint(coordinate_checks("dropoff_lat", "dropoff_lng"), name="valid_dropoff"),
        # A pending order has no driver; assigned/picked up/delivered orders always have one.
        CheckConstraint(
            "(status = 'pending' AND driver_id IS NULL) OR status = 'failed' "
            "OR (status IN ('assigned', 'picked_up', 'delivered') AND driver_id IS NOT NULL)",
            name="driver_matches_status",
        ),
        # A driver can only pick up an order they have accepted.
        CheckConstraint(
            "status NOT IN ('picked_up', 'delivered') OR accepted_at IS NOT NULL",
            name="accepted_before_pickup",
        ),
        # Core conflict guard: a driver can hold at most one active order at a time.
        # Even if application-level locking had a bug, the database rejects a second one.
        Index(
            "uq_orders_driver_active",
            "driver_id",
            unique=True,
            postgresql_where=text(_in_list("status", ACTIVE_ORDER_STATUSES)),
        ),
        # Supports the default listing: filter by status, newest first.
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        enum_column(OrderStatus, "order_status"),
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
    )

    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(20))
    pickup_address: Mapped[str] = mapped_column(String(255))
    pickup_lat: Mapped[float]
    pickup_lng: Mapped[float]
    dropoff_address: Mapped[str] = mapped_column(String(255))
    dropoff_lat: Mapped[float]
    dropoff_lng: Mapped[float]
    notes: Mapped[str | None] = mapped_column(Text)

    # Delivery deadline; orders still open after it are flagged as overdue.
    deliver_by: Mapped[datetime]
    is_overdue: Mapped[bool] = mapped_column(default=False, server_default=false())
    # How many times dispatch has handed this order to a driver.
    assignment_attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    # Lifecycle timestamps.
    assigned_at: Mapped[datetime | None]
    accepted_at: Mapped[datetime | None]
    picked_up_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    business: Mapped["Business"] = relationship(back_populates="orders")
    driver: Mapped["Driver | None"] = relationship(back_populates="orders")
    assignments: Mapped[list["OrderAssignment"]] = relationship(
        back_populates="order", order_by="OrderAssignment.assigned_at"
    )


class OrderAssignment(UUIDPrimaryKeyMixin, Base):
    """One attempt to give an order to a driver.

    Keeps the full history (who was offered the order, who let it expire), so the
    reassignment job can skip drivers that already timed out on the same order.
    """

    __tablename__ = "order_assignments"
    __table_args__ = (
        # An order is bound to at most one driver at a time.
        Index(
            "uq_order_assignments_order_open",
            "order_id",
            unique=True,
            postgresql_where=text(_in_list("status", OPEN_ASSIGNMENT_STATUSES)),
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        enum_column(AssignmentStatus, "assignment_status"),
        default=AssignmentStatus.OFFERED,
        server_default=AssignmentStatus.OFFERED.value,
    )
    assigned_at: Mapped[datetime] = mapped_column(server_default=func.now())
    accepted_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]

    order: Mapped["Order"] = relationship(back_populates="assignments")
