"""Schemas for users and their role-specific profiles."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BusinessCategory, DriverStatus, UserRole, VehicleType
from app.schemas.common import Email, Latitude, Longitude, NonEmptyStr, Password, Phone


class BusinessProfileIn(BaseModel):
    name: Annotated[NonEmptyStr, Field(max_length=120)]
    category: BusinessCategory
    phone: Phone
    address: Annotated[NonEmptyStr, Field(max_length=255)]
    lat: Latitude
    lng: Longitude


class DriverProfileIn(BaseModel):
    phone: Phone
    vehicle_type: VehicleType


class _RegisterBase(BaseModel):
    email: Email
    password: Password
    full_name: Annotated[NonEmptyStr, Field(max_length=120)]


class BusinessRegister(_RegisterBase):
    business: BusinessProfileIn


class DriverRegister(_RegisterBase):
    driver: DriverProfileIn


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: BusinessCategory
    phone: str
    address: str
    lat: float
    lng: float


class DriverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    vehicle_type: VehicleType
    status: DriverStatus
    current_lat: float | None
    current_lng: float | None
    location_updated_at: datetime | None


class UserRead(BaseModel):
    """A user together with their business or driver profile (if any)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    business: BusinessRead | None = None
    driver: DriverRead | None = None
