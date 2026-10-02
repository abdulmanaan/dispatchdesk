"""Load the Lahore demo data set.

    uv run python -m app.scripts.seed_demo            # only if no demo data exists yet
    uv run python -m app.scripts.seed_demo --reset    # WIPE ALL DATA, then seed

``--reset`` truncates every table. Use it only on a demo database.
"""

import argparse
import asyncio
import sys

from app.db.session import SessionLocal, engine
from app.demo.seed import seed_demo


async def _main(reset: bool) -> int:
    try:
        async with SessionLocal() as session:
            summary = await seed_demo(session, reset=reset)
    finally:
        await engine.dispose()

    if summary.skipped:
        print("Demo data already exists. Use --reset to wipe and reseed.")
        return 0
    print(f"Seeded {summary.users} users and {summary.orders} orders: {summary.by_stage}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DispatchDesk demo data (Lahore).")
    parser.add_argument(
        "--reset", action="store_true", help="delete ALL existing data before seeding"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.reset)))


if __name__ == "__main__":
    main()
