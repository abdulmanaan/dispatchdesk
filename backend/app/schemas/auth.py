"""Schemas for authentication responses."""

from typing import Literal

from pydantic import BaseModel

from app.models.enums import UserRole
from app.schemas.user import UserRead


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds
    user: UserRead


class DemoAccount(BaseModel):
    role: UserRole
    full_name: str
    description: str


class DemoInfo(BaseModel):
    """Whether one-click demo logins are available, and for whom."""

    enabled: bool
    accounts: list[DemoAccount]


class DemoLogin(BaseModel):
    role: UserRole
