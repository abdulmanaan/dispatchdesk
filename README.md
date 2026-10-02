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
| Frontend | React, Vite, Tailwind CSS                                   |
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
docker compose up -d
```

This starts PostgreSQL (`localhost:5432`, plus a `dispatchdesk_test` database) and Redis (`localhost:6379`).
