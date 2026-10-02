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

## Tests and linting

Requires the Postgres container from the root `docker-compose.yml` (it creates the `dispatchdesk_test` database).

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
