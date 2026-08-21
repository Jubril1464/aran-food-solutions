# Collective Agricultural Procurement & Food Distribution Platform — MVP

Households, individuals, and small food businesses place orders for agricultural
commodities (rice, beans, garri, etc.). Orders are pooled into time-boxed
**procurement cycles**, aggregated into bulk purchases, then split back into
customer-specific deliveries.

This repo contains the MVP build, scoped strictly to:

- **Priority 1 — Customer:** registration/login, product catalogue, cart, checkout,
  Paystack payment, order tracking, order history, async notifications.
- **Priority 2 — Admin:** product & category management, customer management,
  procurement cycles with demand aggregation and cycle-close.

Suppliers, inventory, quality control, packaging, delivery-partner tracking, demand
forecasting, and full analytics are **out of scope for this pass** — see
[Deferred scope](#deferred-scope) below. Their module folders exist as placeholder
routers only, with no tables, so the codebase boundary is ready for that phase.

## Stack

- **Backend:** FastAPI (modular monolith) + SQLAlchemy 2.0 (async) + PostgreSQL + Alembic
- **Hosting:** Render (native Python web service + static site) + Neon Postgres —
  no Docker, no containers, free tier
- **Background jobs:** pluggable — an in-process background task by default,
  or Redis + [arq](https://arq-docs.helpmanual.io/) with a dedicated worker
  process (what `docker-compose.yml` runs)
- **Frontend:** React + TypeScript (Vite) + Tailwind CSS
- **Auth:** JWT access token (in-memory on the client) + refresh token in an httpOnly cookie
- **Payments:** Paystack, with a built-in **mock mode** (see below) so the full
  checkout → payment → order-confirmed flow works without a real Paystack account
- **Storage:** pluggable — local disk by default, S3-compatible via env var
- **Email:** pluggable — logs to console by default, SMTP via env var

## Deploying it

Hosted on **Render + Neon**, both free, both without a credit card, and with no
Docker anywhere in the process:

| Piece | Where |
|---|---|
| API (FastAPI) | Render web service, native Python — `pip install` + `uvicorn`, straight from this repo |
| Frontend (React) | Render static site — `npm run build`, served as plain files |
| Database | Neon Postgres — its free tier is permanent, unlike Render's, which is deleted after 30 days |

Both services are declared in [`render.yaml`](render.yaml), so the deployment is
created from this repo rather than by clicking through a dashboard.
[`backend/start.sh`](backend/start.sh) applies migrations and ensures an admin
account exists on every boot — both idempotent — so there is no separate release
command to remember, which matters on a free tier with no one-off jobs.

**Full runbook, including the free-tier limitations that actually bite (the API
sleeps after 15 minutes idle; uploaded images aren't persistent), is in
[DEPLOY.md](DEPLOY.md).**

## Running it

### Without Docker (recommended — matches how it's deployed)

Backend:

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at a local Postgres, or see note below
alembic upgrade head
python -m app.seed     # creates the admin + starter catalogue (set SEED_ADMIN_PASSWORD first)
uvicorn app.main:app --reload
```

Notifications are delivered by a background task in the same process, so there is
nothing else to run.

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### With Docker

```bash
cp backend/.env.example backend/.env   # fill in secrets for anything beyond local dev
cp frontend/.env.example frontend/.env
docker compose up --build
```

This starts Postgres, Redis, the API (`http://localhost:8000`, docs at `/docs`),
a dedicated arq notification worker (`QUEUE_BACKEND=redis`), and the frontend
(`http://localhost:5173`). The backend container runs `alembic upgrade head`
before starting. Useful for exercising the queue-backed delivery path — the
deployment itself uses no containers.

> The backend targets Postgres in production (`DATABASE_URL=postgresql+asyncpg://...`),
> but is fully portable to SQLite for quick local hacking without installing Postgres
> (`DATABASE_URL=sqlite+aiosqlite:///./dev.db`) — the test suite runs entirely on
> SQLite for this reason. Redis is only needed if you set `QUEUE_BACKEND=redis` to
> run notification delivery through a separate arq worker; the default
> (`in_process`) delivers in a background task and needs nothing extra.

### Paystack mock mode

Leave `PAYSTACK_SECRET_KEY` blank in `backend/.env` and the payment module runs in
mock mode: `/payments/initialize` returns a link to an in-app mock checkout page
(`/mock-paystack-checkout`) instead of a real Paystack URL, and `/payments/{ref}/verify`
always reports success. This lets the entire checkout flow be exercised end-to-end
without a Paystack account. Set a real secret key to integrate with the live API.

### Tests

```bash
cd backend
pytest
```

The suite runs against a throwaway SQLite database and a mocked notification queue
(no live Postgres/Redis required).

`tests/test_flow.py` covers the business flow: register → verify → login →
password reset round trip, MOQ enforcement at add-to-cart, checkout rejecting a
closed/absent procurement cycle, the full checkout → Paystack (mock) →
order-state-machine flow including **webhook/verify idempotency** (replaying it
doesn't double-apply), demand aggregation correctness, and the
one-open-cycle-per-category rule.

`tests/test_deployment.py` covers what the hosted deployment adds: that a
managed provider's connection string is rewritten into something asyncpg
accepts, that in-process notification delivery actually delivers (including when
the background task starts before the enqueuing transaction has committed), that
`PENDING` notifications left by a dead process are swept up on startup, and —
learned the hard way — that the **seeded admin can actually log in**. A seeded
`admin@agric.local` writes to the database happily and is then rejected by
`EmailStr` at login, because `.local` is a reserved special-use name; nothing
else in the suite would have caught an admin account that exists but can never
authenticate.

## Architecture notes

- **Order lifecycle** is an explicit state machine (`app/models/order.py`,
  `ALLOWED_TRANSITIONS`) — every transition is validated, not just written blindly.
  Only `PENDING_PAYMENT → PAID → CONFIRMED → AGGREGATING → PROCUREMENT` are reachable
  in this phase (via payment verification and cycle-close); later states are wired
  into the model for the Operations phase to advance.
- **Checkout → procurement cycle resolution**: each cart line item resolves the
  currently open cycle for its product (or its category, if the product isn't pinned
  to a specific cycle) at checkout time — see
  `app/modules/procurement/service.py::get_active_cycle_for_product`. If an order's
  items end up split across cycles, cycle-close only auto-advances orders that are
  **entirely** within the closing cycle; this is a deliberate MVP simplification
  (documented in `close_cycle`) since the common path is one open cycle per category.
- **Payment idempotency**: a `Payment` row is uniquely keyed on `(provider, reference)`
  and locked (`SELECT ... FOR UPDATE`) before being applied; once it reaches a
  terminal state (`successful`/`failed`) any further verify call — a duplicate
  webhook delivery, a manual retry — is a no-op.
- **Notifications** are never sent inline: every trigger point persists a
  `Notification` row and enqueues delivery via a pluggable `NotificationQueue`
  (`app/core/queue.py`). Two transports: `in_process` (default — an asyncio
  background task, so no Redis and no second service, which is what lets the app
  run on a single free instance) and `redis` (an arq queue with a dedicated
  worker process, what `docker-compose.yml` runs). Delivery then goes through a
  pluggable `NotificationChannel` (console-log in dev, SMTP for real email; SMS
  is stubbed for a future phase). Delivery is **idempotent and retried**:
  re-delivering an already-sent notification is a no-op, a not-yet-committed row
  is retried rather than dropped, and anything left `PENDING` by a process that
  died is swept up on the next startup (`redeliver_pending`).
- **Audit log**: admin actions that change product price/availability, procurement
  cycle status, or order state are recorded in `admin_audit_log`.
- **There is no self-service route to an admin account** — `/auth/register` only
  ever creates customers, by design. The first administrator is created by a
  one-off bootstrap step (`app/seed.py`, run by `backend/start.sh` on every boot),
  which also seeds a starter catalogue and one open procurement cycle per category
  so a fresh deployment is demonstrable rather than empty. It's idempotent, and
  re-running it extends an expired order window.
- **Deployment-shaped details are configuration, not forks**: the same code runs
  locally and hosted. `DATABASE_URL` is normalised so a managed provider's
  connection string works as pasted (`postgresql://…?sslmode=require` becomes
  asyncpg-safe — see `normalize_database_url`); the refresh cookie switches to
  `SameSite=None` because the hosted frontend and API sit on different
  hostnames; the notification transport and file storage are chosen by env var.
  All of it is spelled out in [DEPLOY.md](DEPLOY.md).

## Deferred scope

Not built in this pass (see the PRD, §14–17/20–21/29–30): supplier management,
supplier quotations, purchase orders, inventory/quality control, packaging,
delivery-partner tracking, demand forecasting, supplier scoring, full analytics.
Their routers exist under `app/modules/{suppliers,inventory,packaging,delivery}`
as 501-returning placeholders so the module boundary is in place; `analytics`
exposes only the basic counts the MVP scope calls for.
