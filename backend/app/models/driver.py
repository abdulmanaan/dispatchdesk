"""Drivers who pick up and deliver orders."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DriverStatus, VehicleType, enum_column
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, coordinate_checks

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Driver(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "drivers"
    __table_args__ = (
        # Location is either fully known or fully unknown.
        CheckConstraint(
            "(current_lat IS NULL) = (current_lng IS NULL)", name="location_both_or_neither"
        ),
        CheckConstraint(
            f"current_lat IS NULL OR ({coordinate_checks('current_lat', 'current_lng')})",
            name="valid_coordinates",
        ),
    )

    # One driver profile per driver-role user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    phone: Mapped[str] = mapped_column(String(20))
    vehicle_type: Mapped[VehicleType] = mapped_column(enum_column(VehicleType, "vehicle_type"))
    status: Mapped[DriverStatus] = mapped_column(
        enum_column(DriverStatus, "driver_status"),
        default=DriverStatus.OFFLINE,
        server_default=DriverStatus.OFFLINE.value,
        index=True,
    )
    current_lat: Mapped[float | None]
    current_lng: Mapped[float | None]
    location_updated_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="driver")
    orders: Mapped[list["Order"]] = relationship(back_populates="driver")
