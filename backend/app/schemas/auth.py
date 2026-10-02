"""Schemas for authentication responses."""

from typing import Literal

from pydantic import BaseModel

from app.schemas.user import UserRead


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds
    user: UserRead
