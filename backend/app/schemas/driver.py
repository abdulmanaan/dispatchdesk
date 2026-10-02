"""Schemas for driver self-service and the admin driver list."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DriverStatus, VehicleType
from app.schemas.common import Latitude, Longitude
from app.schemas.pagination import PageParams


class LocationUpdate(BaseModel):
    lat: Latitude
    lng: Longitude


class DriverStatusUpdate(BaseModel):
    """A driver going online or offline. ``busy`` is set by the system only."""

    status: Literal[DriverStatus.AVAILABLE, DriverStatus.OFFLINE]
    # Optional location, so "go online here" is a single request.
    lat: Latitude | None = None
    lng: Longitude | None = None

    @model_validator(mode="after")
    def _location_pair(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be given together")
        return self


class DriverListParams(PageParams):
    status: list[DriverStatus] = []
    vehicle_type: VehicleType | None = None
    # Case-insensitive match on name, email or phone.
    search: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class DriverAdminRead(BaseModel):
    """A driver as shown in the admin dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    phone: str
    vehicle_type: VehicleType
    status: DriverStatus
    current_lat: float | None
    current_lng: float | None
    location_updated_at: datetime | None
    active_order_id: uuid.UUID | None
    created_at: datetime
