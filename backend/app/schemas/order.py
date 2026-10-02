"""Schemas for delivery orders."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import OrderStatus, VehicleType
from app.schemas.common import Latitude, Longitude, NonEmptyStr, Phone
from app.schemas.pagination import PageParams

# How far ahead a delivery deadline may be set.
MAX_DELIVERY_WINDOW = timedelta(hours=24)

Address = Annotated[NonEmptyStr, Field(max_length=255)]


class OrderCreate(BaseModel):
    customer_name: Annotated[NonEmptyStr, Field(max_length=120)]
    customer_phone: Phone
    dropoff_address: Address
    dropoff_lat: Latitude
    dropoff_lng: Longitude
    # Pickup defaults to the business's own address and location when omitted.
    pickup_address: Address | None = None
    pickup_lat: Latitude | None = None
    pickup_lng: Longitude | None = None
    notes: Annotated[str, Field(max_length=500)] | None = None
    # Defaults to now + the configured delivery window when omitted.
    deliver_by: AwareDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        pickup = (self.pickup_address, self.pickup_lat, self.pickup_lng)
        if any(v is not None for v in pickup) and not all(v is not None for v in pickup):
            raise ValueError("pickup_address, pickup_lat and pickup_lng must be given together")

        if self.deliver_by is not None:
            now = datetime.now(UTC)
            if self.deliver_by <= now:
                raise ValueError("deliver_by must be in the future")
            if self.deliver_by > now + MAX_DELIVERY_WINDOW:
                raise ValueError("deliver_by must be within 24 hours")
        return self


class OrderCancel(BaseModel):
    reason: Annotated[str, Field(max_length=200)] | None = None


class OrderFail(BaseModel):
    """A driver reporting that a delivery could not be completed."""

    reason: Annotated[NonEmptyStr, Field(min_length=3, max_length=200)]


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    driver_id: uuid.UUID | None
    status: OrderStatus
    customer_name: str
    customer_phone: str
    pickup_address: str
    pickup_lat: float
    pickup_lng: float
    dropoff_address: str
    dropoff_lat: float
    dropoff_lng: float
    notes: str | None
    deliver_by: datetime
    is_overdue: bool
    assignment_attempts: int
    assigned_at: datetime | None
    accepted_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


OrderSort = Literal["created_at", "-created_at", "deliver_by", "-deliver_by"]


class OrderListParams(PageParams):
    """Query parameters for listing orders."""

    status: list[OrderStatus] = []
    business_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    is_overdue: bool | None = None
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None
    # Case-insensitive match on customer name, customer phone or drop-off address.
    search: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    sort: OrderSort = "-created_at"


class BusinessBrief(BaseModel):
    id: uuid.UUID
    name: str
    phone: str


class DriverBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str
    vehicle_type: VehicleType


class OrderDetail(OrderRead):
    """An order with the people involved, for detail views (not lists)."""

    business: BusinessBrief
    driver: DriverBrief | None
