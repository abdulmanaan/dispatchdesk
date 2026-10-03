"""Internal endpoints for infrastructure (not for end users).

Called by an external scheduler (a GitHub Actions cron workflow) on hosts that
do not run worker processes. Both require the ``X-Jobs-Token`` header.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.demo.seed import seed_demo
from app.jobs.tasks import run_all_jobs


async def require_jobs_token(x_jobs_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().jobs_token
    if expected is None:
        # Disabled unless configured; do not reveal that the endpoints exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if x_jobs_token is None or not secrets.compare_digest(
        x_jobs_token.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid jobs token")


router = APIRouter(
    prefix="/internal", include_in_schema=False, dependencies=[Depends(require_jobs_token)]
)


@router.post("/jobs/run")
async def run_jobs(session: DbSession) -> dict[str, int]:
    """Run all background jobs once."""
    report = await run_all_jobs(session)
    return report.as_dict()


@router.post("/demo/reset")
async def reset_demo(session: DbSession) -> dict[str, object]:
    """Wipe all data and reseed the demo (demo mode only).

    Scheduled daily on the public demo, so the "last 24 hours" history stays
    fresh and whatever visitors created is cleared.
    """
    if not get_settings().demo_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    summary = await seed_demo(session, reset=True)
    return {"users": summary.users, "orders": summary.orders}
