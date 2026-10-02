"""Dashboard statistics."""

from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import AdminUser, DbSession
from app.core.cache import get_or_set_json
from app.core.config import get_settings
from app.schemas.stats import StatsOverview
from app.services.stats import compute_overview

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
async def stats_overview(_admin: AdminUser, session: DbSession, response: Response) -> Any:
    """Order/driver counts and last-24h delivery performance (admin only).

    Cached briefly in Redis because dashboards poll it. Data changes on nearly
    every request (location pings, dispatch, jobs), so a short TTL is used
    instead of invalidation. ``X-Cache`` tells whether the cache was hit.
    """
    data, hit = await get_or_set_json(
        "stats:overview",
        get_settings().cache_stats_ttl_seconds,
        lambda: compute_overview(session),
    )
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return data
