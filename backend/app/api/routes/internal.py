"""Internal endpoints for infrastructure (not for end users).

``POST /internal/jobs/run`` lets an external scheduler (e.g. a GitHub Actions
cron workflow) execute the background jobs on hosts without worker processes.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.jobs.tasks import run_all_jobs

router = APIRouter(prefix="/internal", include_in_schema=False)


@router.post("/jobs/run")
async def run_jobs(
    session: DbSession, x_jobs_token: Annotated[str | None, Header()] = None
) -> dict[str, int]:
    """Run all background jobs once. Requires the ``X-Jobs-Token`` header."""
    expected = get_settings().jobs_token
    if expected is None:
        # Disabled unless configured; do not reveal that the endpoint exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if x_jobs_token is None or not secrets.compare_digest(
        x_jobs_token.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid jobs token")

    report = await run_all_jobs(session)
    return report.as_dict()
