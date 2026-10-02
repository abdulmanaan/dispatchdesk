"""Schemas for manual (admin-triggered) dispatch."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.order import OrderRead
from app.services.dispatch import DispatchOutcome


class DispatchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    outcome: DispatchOutcome
    driver_id: uuid.UUID | None
    distance_km: float | None
    candidates: int


class DispatchOrderResponse(BaseModel):
    result: DispatchResultRead
    order: OrderRead


class DispatchRunResponse(BaseModel):
    attempted: int
    assigned: int
    results: list[DispatchResultRead]
