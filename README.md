# DispatchDesk

A local delivery dispatch and driver management system. Small businesses (restaurants, pharmacies, shops) create delivery orders, and DispatchDesk auto-assigns them to the best available driver without conflicts.

> Work in progress. Built step by step.

## Features (planned)

- Role-based access: admin, business, driver
- Auto-dispatch by distance (haversine), workload and availability
- Order lifecycle: `pending → assigned → picked_up → delivered / failed`
- Conflict-free assignment using PostgreSQL transactions and row locking
- Background jobs: reassign unaccepted orders, flag overdue deliveries
- Redis caching and rate limiting, audit logs, filtering and pagination
- One-click demo logins with seeded data around Lahore

## Tech stack

| Layer    | Tech                                                        |
| -------- | ----------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy (async), Alembic, uv       |
| Data     | PostgreSQL (Neon in production), Redis                      |
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query |
| Dev      | Docker Compose                                              |

## Repository layout

```
backend/    FastAPI application
frontend/   React + Vite application
docker/     Local infrastructure helpers
```

## Local development

```bash
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up -d
```

| Service  | URL                          | Notes                                        |
| -------- | ---------------------------- | -------------------------------------------- |
| Frontend | http://localhost:5173        | Vite dev server; `/api` is proxied to the backend |
| Backend  | http://localhost:8000/docs   | Interactive API docs                         |
| Postgres | `localhost:5433`             | Also creates `dispatchdesk_test` for tests   |
| Redis    | `localhost:6379`             | Cache and rate limits                        |

The `worker` service runs the background jobs. Create a first admin with
`docker compose exec backend python -m app.scripts.create_admin --email you@example.com`.

See [backend/README.md](backend/README.md) for API details.

### Frontend without Docker

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
npm test           # unit and component tests (Vitest)
npm run lint && npm run typecheck
```
