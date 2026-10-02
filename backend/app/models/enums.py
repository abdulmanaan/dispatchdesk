"""Domain enumerations and the column type used to store them."""

from enum import StrEnum

from sqlalchemy import Enum


class UserRole(StrEnum):
    ADMIN = "admin"
    BUSINESS = "business"
    DRIVER = "driver"


class BusinessCategory(StrEnum):
    RESTAURANT = "restaurant"
    PHARMACY = "pharmacy"
    GROCERY = "grocery"
    RETAIL = "retail"
    OTHER = "other"


class VehicleType(StrEnum):
    MOTORBIKE = "motorbike"
    CAR = "car"
    BICYCLE = "bicycle"


class DriverStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class OrderStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    FAILED = "failed"


# Statuses in which an order occupies its driver.
ACTIVE_ORDER_STATUSES = (OrderStatus.ASSIGNED, OrderStatus.PICKED_UP)
# Statuses in which an order is not finished yet.
OPEN_ORDER_STATUSES = (OrderStatus.PENDING, *ACTIVE_ORDER_STATUSES)


class AssignmentStatus(StrEnum):
    """Outcome of a single attempt to hand an order to a driver."""

    OFFERED = "offered"  # assigned, waiting for the driver to accept
    ACCEPTED = "accepted"  # driver accepted and is working on the order
    EXPIRED = "expired"  # driver did not accept in time, order was reassigned
    COMPLETED = "completed"  # order delivered
    FAILED = "failed"  # order failed while with this driver


# Assignment statuses that still bind the order to the driver.
OPEN_ASSIGNMENT_STATUSES = (AssignmentStatus.OFFERED, AssignmentStatus.ACCEPTED)


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store a StrEnum as VARCHAR + CHECK constraint (by value, not member name).

    A non-native enum avoids PostgreSQL ``ALTER TYPE`` migrations when values change.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        validate_strings=True,
        values_callable=lambda members: [m.value for m in members],
    )
