"""Create an admin account from the command line.

Admins cannot self-register through the API. Usage:

    uv run python -m app.scripts.create_admin --email admin@example.com --name "Admin"

The password is read from the ADMIN_PASSWORD environment variable or prompted for.
"""

import argparse
import asyncio
import getpass
import os
import sys

from app.db.session import SessionLocal, engine
from app.services.auth import EmailAlreadyRegisteredError, create_admin


async def _main(email: str, name: str, password: str) -> int:
    try:
        async with SessionLocal() as session:
            user = await create_admin(session, email=email, password=password, full_name=name)
    except EmailAlreadyRegisteredError:
        print(f"An account with email {email} already exists.", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(f"Created admin {user.email} ({user.id})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a DispatchDesk admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    if len(password) < 8:
        parser.error("password must be at least 8 characters")

    sys.exit(asyncio.run(_main(args.email, args.name, password)))


if __name__ == "__main__":
    main()
