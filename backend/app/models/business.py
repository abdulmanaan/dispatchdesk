"""Businesses (restaurants, pharmacies, shops) that create delivery orders."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BusinessCategory, enum_column
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, coordinate_checks

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Business(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (CheckConstraint(coordinate_checks("lat", "lng"), name="valid_coordinates"),)

    # One business profile per business-role user.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[BusinessCategory] = mapped_column(
        enum_column(BusinessCategory, "business_category")
    )
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    # Default pickup location for this business's orders.
    lat: Mapped[float]
    lng: Mapped[float]

    owner: Mapped["User"] = relationship(back_populates="business")
    orders: Mapped[list["Order"]] = relationship(back_populates="business")
