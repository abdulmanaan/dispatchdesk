"""Aggregate numbers for the admin dashboard."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, Order
from app.models.enums import OPEN_ORDER_STATUSES, DriverStatus, OrderStatus


async def _counts_by_status(session: AsyncSession, column: Any, enum: type) -> dict[str, int]:
    rows = (await session.execute(select(column, func.count()).group_by(column))).all()
    counts = {member.value: 0 for member in enum}
    counts.update({status.value: count for status, count in rows})
    return counts


async def compute_overview(session: AsyncSession) -> dict[str, Any]:
    """Order and driver counts plus delivery performance over the last 24 hours."""
    now = datetime.now(UTC)
    since = now - timedelta(hours=24)

    overdue_open = await session.scalar(
        select(func.count()).where(Order.status.in_(OPEN_ORDER_STATUSES), Order.is_overdue)
    )

    delivered = (
        select(Order)
        .where(Order.status == OrderStatus.DELIVERED, Order.delivered_at >= since)
        .subquery()
    )
    delivered_count, on_time_count, avg_seconds = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(delivered.c.delivered_at <= delivered.c.deliver_by),
                func.avg(func.extract("epoch", delivered.c.delivered_at - delivered.c.created_at)),
            ).select_from(delivered)
        )
    ).one()
    failed_count = await session.scalar(
        select(func.count()).where(Order.status == OrderStatus.FAILED, Order.failed_at >= since)
    )

    return {
        "orders_by_status": await _counts_by_status(session, Order.status, OrderStatus),
        "drivers_by_status": await _counts_by_status(session, Driver.status, DriverStatus),
        "overdue_open_orders": overdue_open or 0,
        "last_24h": {
            "delivered": delivered_count,
            "failed": failed_count or 0,
            "on_time_rate": round(on_time_count / delivered_count, 3) if delivered_count else None,
            "avg_delivery_minutes": round(float(avg_seconds) / 60, 1) if avg_seconds else None,
        },
        "generated_at": now.isoformat(),
    }
