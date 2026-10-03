# Deploying DispatchDesk (free tiers, no credit card)

| Part | Service | Free plan used |
| --- | --- | --- |
| Backend API | [FastAPI Cloud](https://fastapicloud.com) | Hobby (public beta): 3 apps, scales to zero when idle |
| Database | [Neon](https://neon.com) Postgres | 100 compute-hours/month, 0.5 GB, sleeps after 5 idle minutes |
| Cache and rate limits | [Upstash](https://upstash.com) Redis | 500K commands/month, 256 MB |
| Frontend | [Vercel](https://vercel.com) | Hobby |
| Background jobs and deploys | GitHub Actions | Free for public repositories |

Free hosting doesn't run worker processes, so the jobs run in two ways:

- **`.github/workflows/jobs.yml`** calls `POST /internal/jobs/run` every 15 minutes and
  `POST /internal/demo/reset` once a day at 03:00 Lahore time. Every 15 minutes rather than 5,
  because each call wakes Neon, and its free plan allows 100 compute-hours a month.
- **The demo heartbeat**: while people are using the demo, normal API traffic also runs the jobs
  in the background, at most every 20 seconds. Orders keep moving while someone watches.

`.github/workflows/deploy.yml` runs after CI passes on `main`: it applies Alembic migrations to
Neon, then runs `fastapi deploy`. Until its secrets exist, it skips with a notice instead of failing.

Plan about 30 minutes. Do the steps in order; later steps need values from earlier ones.

## 1. Neon (database)

1. Sign up at neon.com and create a project. Pick the **AWS US East (N. Virginia)** region.
2. In **Connect**, choose the default branch and database, and **turn off "Connection pooling"**.
   The app uses asyncpg with its own connection pool, which works best with a direct connection.
3. Copy the connection string. It looks like
   `postgresql://neondb_owner:...@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
   Paste it as-is everywhere below: the app converts it for asyncpg automatically.

## 2. Upstash (Redis)

1. Sign up at upstash.com and create a Redis database in a nearby AWS US East region.
2. Copy the **TLS** connection URL: `rediss://default:<password>@<name>.upstash.io:6379`
   (note the double `s`).

## 3. Generate two secrets

```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('JOBS_TOKEN=' + secrets.token_urlsafe(32))"
```

## 4. Create the database tables

From your machine (one time; afterwards the deploy workflow does it):

```bash
cd backend
DATABASE_URL='<Neon connection string>' uv run alembic upgrade head
```

## 5. FastAPI Cloud (backend)

1. Create `backend/.env.production` (git and the deploy both ignore it) with:

   ```env
   ENVIRONMENT=production
   JWT_SECRET_KEY=<from step 3>
   JOBS_TOKEN=<from step 3>
   DATABASE_URL=<Neon connection string>
   REDIS_URL=<Upstash rediss:// URL>
   CORS_ORIGINS=http://localhost:5173
   DEMO_MODE=true
   DISPATCH_LOCATION_MAX_AGE_MINUTES=0
   TRUSTED_PROXY_HOPS=1
   ```

   `CORS_ORIGINS` gets the real Vercel URL in step 7. `DISPATCH_LOCATION_MAX_AGE_MINUTES=0`
   is needed because seeded demo drivers never send fresh locations.

2. Deploy for the first time (this creates the app):

   ```bash
   cd backend
   uv run fastapi login
   uv run fastapi deploy
   ```

   Accept the suggested settings. The app is found through `[tool.fastapi] entrypoint` in
   `pyproject.toml`, and the **application directory** setting stays empty, because the deploy
   runs from inside `backend/`.

3. In the FastAPI Cloud dashboard, open the app, then **Environment Variables**, and use
   **import** with `backend/.env.production`. Mark `JWT_SECRET_KEY`, `JOBS_TOKEN`,
   `DATABASE_URL` and `REDIS_URL` as **secret** (this can only be chosen when a variable is
   created). Then click **Save and Redeploy**.

4. Note the app URL (for example `https://dispatchdesk.fastapicloud.dev`) and check
   `<app URL>/health`. It should return `{"status":"ok","database":"ok"}`.

5. Load the demo data:

   ```bash
   curl -X POST -H "X-Jobs-Token: <JOBS_TOKEN>" <app URL>/internal/demo/reset
   # {"users":14,"orders":27}
   ```

## 6. Vercel (frontend)

1. Sign up at vercel.com with GitHub and **import** the `dispatchdesk` repository.
2. Set **Root Directory** to `frontend`. Vercel detects Vite; `frontend/vercel.json` already
   sets the build, the SPA fallback for client-side routes and asset caching.
3. Add the environment variable `VITE_API_URL` = your FastAPI Cloud app URL (no trailing slash).
4. Deploy, and note the URL (for example `https://dispatchdesk.vercel.app`).

## 7. Allow the frontend to call the API

In FastAPI Cloud, set `CORS_ORIGINS` to the Vercel URL (comma-separate several, for example a
custom domain as well), then **Save and Redeploy**.

## 8. GitHub: automatic deploys and scheduled jobs

In the repository: **Settings → Secrets and variables → Actions**.

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `DATABASE_URL` | Neon connection string (for migrations) |
| Secret | `FASTAPI_CLOUD_TOKEN` | FastAPI Cloud dashboard: app, **Deploy Tokens**, **Create Token** (up to 365 days) |
| Secret | `FASTAPI_CLOUD_APP_ID` | The app's ID from the FastAPI Cloud dashboard |
| Secret | `JOBS_TOKEN` | The same value as on FastAPI Cloud |
| Variable | `API_URL` | FastAPI Cloud app URL |

Then open **Actions → Scheduled jobs → Run workflow** once, to check that the call succeeds.

> GitHub pauses scheduled workflows in a repository with no activity for 60 days. If the demo
> stops moving after a long quiet period, re-enable the workflow in the Actions tab.

## 9. Check that everything works

- [ ] `<app URL>/health` returns `ok` for the database.
- [ ] The Vercel site shows **Or try the demo** under the login form.
- [ ] As **Business**, create an order: it is assigned within seconds. Keep the page open; a
      simulated driver accepts, picks up and delivers it over the next few minutes.
- [ ] As **Driver**, Kamran has an order waiting: tap through pickup and delivery.
- [ ] As **Admin**, **Activity** shows those steps.
- [ ] **Actions → Scheduled jobs** shows green runs every 15 minutes.
- [ ] Push a commit: **CI** runs, then **Deploy backend** migrates and deploys.
- [ ] Rate limiting sees real visitor IPs: sign in with a wrong password 11 times from your
      laptop (the 11th returns "Too many requests"), then try once from your phone on mobile data.
      The phone must **not** be blocked. If it is, the platform has two proxies in front of the
      app: set `TRUSTED_PROXY_HOPS=2` and redeploy.

## Fallback: Render instead of FastAPI Cloud

If FastAPI Cloud is unavailable, the backend runs on any Docker host. On Render, create a
**Web Service** from the repository with root directory `backend` (it uses `backend/Dockerfile`)
and the start command
`sh -c "alembic upgrade head && fastapi run --host 0.0.0.0 --port $PORT"`. Use the same environment
variables. Render's free instances also sleep when idle, so everything above (scheduled jobs,
heartbeat) applies unchanged. Check Render's current free-plan terms when you sign up.

## Settings reference

| Variable | Production value | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | Refuses to start with a weak or default JWT secret |
| `JWT_SECRET_KEY` | random, 32+ characters | Signs login tokens |
| `DATABASE_URL` | Neon connection string | `sslmode` is converted for asyncpg automatically |
| `REDIS_URL` | Upstash `rediss://` URL | Optional; without it caching and rate limits switch off |
| `CORS_ORIGINS` | Vercel URL(s), comma-separated | Browser origins allowed to call the API |
| `DEMO_MODE` | `true` | One-click demo logins, simulated drivers, heartbeat, daily reset |
| `DISPATCH_LOCATION_MAX_AGE_MINUTES` | `0` | Seeded demo drivers never move |
| `TRUSTED_PROXY_HOPS` | `1` | Count rate limits per visitor, not per proxy |
| `JOBS_TOKEN` | random | Protects `/internal/jobs/run` and `/internal/demo/reset` |
| `ACCEPTANCE_TIMEOUT_SECONDS` | `180` (default) | How long a driver has to accept |
