"""Long-running worker that executes the background jobs on an interval.

Used for local development (the ``worker`` service in docker-compose). In
production the same jobs are triggered via ``POST /internal/jobs/run`` by an
external scheduler instead, because free hosting tiers do not run workers.

    uv run python -m app.jobs.worker
"""

import asyncio
import contextlib
import logging
import signal

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.jobs.tasks import run_all_jobs

logger = logging.getLogger("app.jobs.worker")


async def run_once() -> None:
    async with SessionLocal() as session:
        report = await run_all_jobs(session)
    if any(report.as_dict().values()):
        logger.info("Jobs run: %s", report.as_dict())


async def run_worker(stop: asyncio.Event, interval_seconds: float) -> None:
    """Run the jobs every ``interval_seconds`` until ``stop`` is set."""
    logger.info("Worker started (interval %ss)", interval_seconds)
    while not stop.is_set():
        try:
            await run_once()
        except Exception:  # a broken run (e.g. DB down) must not kill the worker
            logger.exception("Job run failed")
        # Sleep until the next run, waking early if asked to stop.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
    logger.info("Worker stopped")


async def _main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run_worker(stop, get_settings().jobs_interval_seconds)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_main())
