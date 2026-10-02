# DispatchDesk backend

FastAPI service for DispatchDesk. See the root README for the full project overview.

## Setup

```bash
uv sync                       # creates .venv and installs dependencies
cp .env.example .env
uv run alembic upgrade head   # apply migrations
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs. Health check: http://localhost:8000/health.

## Authentication

- `POST /auth/register/business` and `POST /auth/register/driver` create accounts (drivers start offline).
- `POST /auth/login` takes form fields `username` (email) and `password` and returns a bearer token.
- `GET /auth/me` returns the signed-in user with their profile.

Admins cannot self-register. Create one from the command line:

```bash
uv run python -m app.scripts.create_admin --email admin@example.com --name "Admin"
# or inside Docker:
docker compose exec backend python -m app.scripts.create_admin --email admin@example.com
```

## Background jobs

Three jobs run on every cycle (`app/jobs/tasks.py`):

1. **Expire unaccepted assignments**: orders assigned more than `ACCEPTANCE_TIMEOUT_SECONDS`
   ago and still not accepted go back to `pending` and are re-dispatched. The driver
   is set offline and never offered that order again.
2. **Retry pending orders**: dispatch orders that were created while no driver was free.
3. **Flag overdue orders**: open orders past `deliver_by` get `is_overdue = true`.

All jobs are safe to run concurrently (row locks with `SKIP LOCKED`, atomic updates).

- **Locally**: the `worker` service in docker-compose runs them every `JOBS_INTERVAL_SECONDS`
  (`uv run python -m app.jobs.worker` outside Docker).
- **Production**: set `JOBS_TOKEN` and have a scheduler call
  `POST /internal/jobs/run` with header `X-Jobs-Token: <token>`. The endpoint returns 404
  while `JOBS_TOKEN` is unset.

## Tests and linting

Requires the Postgres container from the root `docker-compose.yml` (it creates the `dispatchdesk_test` database).

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
