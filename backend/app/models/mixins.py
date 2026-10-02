"""Reusable column mixins."""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def coordinate_checks(lat: str, lng: str) -> str:
    """SQL expression that keeps a lat/lng pair within valid WGS84 ranges."""
    return f"{lat} BETWEEN -90 AND 90 AND {lng} BETWEEN -180 AND 180"
