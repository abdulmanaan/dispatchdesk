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

## Tests and linting

Requires the Postgres container from the root `docker-compose.yml` (it creates the `dispatchdesk_test` database).

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
