"""Schemas for dashboard statistics."""

from datetime import datetime

from pydantic import BaseModel


class Last24h(BaseModel):
    delivered: int
    failed: int
    # Share of delivered orders that arrived before their deadline (0..1).
    on_time_rate: float | None
    # Average time from order creation to delivery.
    avg_delivery_minutes: float | None


class StatsOverview(BaseModel):
    orders_by_status: dict[str, int]
    drivers_by_status: dict[str, int]
    overdue_open_orders: int
    last_24h: Last24h
    generated_at: datetime
