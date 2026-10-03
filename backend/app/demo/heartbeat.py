"""Keep the demo moving while people are using it.

On free hosting the jobs only run when a scheduler calls them (every 15 minutes
on the public demo). That is too slow for a visitor watching their order. In
demo mode, normal API traffic also triggers a job run in the background, at most
once per ``HEARTBEAT_SECONDS`` across all instances (coordinated through Redis).
"""

import logging

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.core.redis import REDIS_ERRORS, get_redis, warn_unavailable
from app.db.session import SessionLocal
from app.jobs.tasks import run_all_jobs

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 20
LOCK_KEY = "demo:heartbeat"


async def _run_jobs() -> None:
    try:
        async with SessionLocal() as session:
            report = await run_all_jobs(session)
        logger.info("Demo heartbeat: %s", report.as_dict())
    except Exception:
        logger.exception("Demo heartbeat failed")


async def demo_heartbeat(background_tasks: BackgroundTasks) -> None:
    """Dependency: schedule a job run after this response, if one is due."""
    if not get_settings().demo_mode:
        return
    redis = get_redis()
    if redis is None:
        return
    try:
        # SET NX EX: only the first request in each window wins the right to run.
        due = await redis.set(LOCK_KEY, "1", nx=True, ex=HEARTBEAT_SECONDS)
    except REDIS_ERRORS as exc:
        warn_unavailable(exc)
        return
    if due:
        background_tasks.add_task(_run_jobs)
