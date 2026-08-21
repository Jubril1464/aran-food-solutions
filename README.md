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
- **Runtime:** AWS Lambda in the cloud (zip package + dependency layer, via
  [Mangum](https://mangum.io/)), uvicorn locally — same code either way
- **Background jobs:** Redis + [arq](https://arq-docs.helpmanual.io/) locally,
  SQS + a consumer Lambda on AWS (notification delivery)
- **Frontend:** React + TypeScript (Vite) + Tailwind CSS
- **Auth:** JWT access token (in-memory on the client) + refresh token in an httpOnly cookie
- **Payments:** Paystack, with a built-in **mock mode** (see below) so the full
  checkout → payment → order-confirmed flow works without a real Paystack account
- **Storage:** pluggable — local disk by default, S3-compatible via env var
- **Email:** pluggable — logs to console by default, SMTP via env var

## Deploying to AWS

The backend runs **fully serverless on AWS Lambda** — no always-on server.
Terraform for a fresh AWS account lives in [`infra/`](infra/): four Lambda
functions sharing one zip artifact and one dependency layer, plus RDS Postgres
and S3 + CloudFront for the frontend, built to run as close to zero recurring
cost as possible for pitching rather than production traffic. **Deploying needs
no Docker** — `infra/scripts/build-lambda-package.py` fetches Linux wheels with
pip from any OS, and Terraform uploads the zips itself.

| Function | Entrypoint | Triggered by |
|---|---|---|
| API | [`app/lambda_handler.py`](backend/app/lambda_handler.py) — Mangum → FastAPI | API Gateway HTTP API |
| Notification worker | [`app/notification_worker_handler.py`](backend/app/notification_worker_handler.py) | SQS |
| Migration runner | [`app/migration_handler.py`](backend/app/migration_handler.py) — `alembic upgrade head` | manual invoke, as a deploy step |
| Bootstrap / seed | [`app/seed_handler.py`](backend/app/seed_handler.py) — first admin + starter catalogue | manual invoke, once after the first deploy |

The same code still runs as a normal uvicorn process for local development
(`docker-compose.yml`), which is what the "Running it" section below uses —
the Lambda-specific paths key off `AWS_LAMBDA_FUNCTION_NAME` and
`QUEUE_BACKEND=sqs` rather than forking the codebase.

See [`infra/DEPLOY.md`](infra/DEPLOY.md) for the first-deploy runbook, what
running on Lambda changes about the app (connection pooling, the cross-site
refresh cookie, upload limits, at-least-once notifications, cold starts), the
explicit cost/security trade-off it makes (a publicly-reachable database, to
avoid a NAT gateway), and the cost breakdown. It's written and
`terraform validate`-clean but has not been applied; provisioning real
infrastructure is a deliberate step you take yourself.

## Running it

### With Docker (recommended)

```bash
cp backend/.env.example backend/.env   # fill in secrets for anything beyond local dev
cp frontend/.env.example frontend/.env
docker compose up --build
```

This starts Postgres, Redis, the API (`http://localhost:8000`, docs at `/docs`),
the arq notification worker, and the frontend (`http://localhost:5173`). The
backend container runs `alembic upgrade head` before starting.

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at a local Postgres, or see note below
alembic upgrade head
uvicorn app.main:app --reload
# in a second terminal, for notifications to actually send:
arq app.worker.WorkerSettings
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

> The backend targets Postgres in production (`DATABASE_URL=postgresql+asyncpg://...`),
> but is fully portable to SQLite for quick local hacking without installing Postgres
> (`DATABASE_URL=sqlite+aiosqlite:///./dev.db`) — the test suite runs entirely on
> SQLite for this reason. Redis is required for any request that triggers a
> notification (register, checkout, payment, cycle close) since those are enqueued
> asynchronously rather than sent inline — there is no in-process fallback.

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

`tests/test_lambda_handlers.py` covers the serverless entrypoints by driving
the real handlers with synthetic API Gateway and SQS events in a subprocess (a
fresh process being the honest stand-in for a cold start, and re-invoking in it
for a warm one): Mangum's event translation, a database query on a *warm*
invocation, the cross-site refresh cookie, Lambda's injected AWS credentials not
shadowing the S3 client's, `NullPool`, and SQS partial-batch-failure reporting —
including that a failed send is retried rather than silently dropped. It also
covers the bootstrap step: that seeding is idempotent, and that afterwards the
admin can log in and the public catalogue isn't empty.

`tests/test_lambda_package.py` guards the deployment package itself, with no AWS
involved: that `requirements-lambda.txt` never disagrees with `requirements.txt`,
that every third-party module `app/` imports will actually exist on Lambda, and
that nothing a handler imports drags in `arq`/`redis` — the dependencies left out
of the layer, which only stays safe while those imports remain lazy.

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
  `Notification` row and enqueues a job via a pluggable `NotificationQueue`
  (`app/core/queue.py`) — arq/Redis by default (local dev, `docker-compose.yml`),
  or SQS when `QUEUE_BACKEND=sqs` (the AWS Lambda deployment in `infra/`, where
  a separate Lambda consumes the queue). Either way, delivery goes through a
  pluggable `NotificationChannel` (console-log in dev, SMTP for real email;
  SMS is stubbed for a future phase). Delivery is **at-least-once and
  idempotent**: `send_notification` raises on failure so the consumer retries
  (arq locally, SQS redelivery → DLQ on Lambda), and re-delivering an
  already-sent notification is a no-op.
- **Audit log**: admin actions that change product price/availability, procurement
  cycle status, or order state are recorded in `admin_audit_log`.
- **There is no self-service route to an admin account** — `/auth/register` only
  ever creates customers, by design. The first administrator is created by a
  one-off bootstrap step (`app/seed_handler.py`, run as a Lambda on AWS), which
  also seeds a starter catalogue and one open procurement cycle per category so
  a fresh deployment is demonstrable rather than empty. It's idempotent, and
  re-running it extends an expired order window.
- **One codebase, two runtimes**: the same modules serve a long-running uvicorn
  process and an AWS Lambda function. Where the two genuinely differ, the
  difference is explicit and keyed off the environment rather than forked — a
  `NullPool` engine when `AWS_LAMBDA_FUNCTION_NAME` is set (Lambda gives each
  invocation a fresh event loop, which a pooled asyncpg connection cannot
  survive), SQS instead of arq via `QUEUE_BACKEND`, S3 instead of local disk for
  uploads, and a `SameSite=None` refresh cookie because CloudFront and API
  Gateway are different sites. Each of these is spelled out in
  [`infra/DEPLOY.md`](infra/DEPLOY.md#what-running-on-lambda-changes-about-the-app).

## Deferred scope

Not built in this pass (see the PRD, §14–17/20–21/29–30): supplier management,
supplier quotations, purchase orders, inventory/quality control, packaging,
delivery-partner tracking, demand forecasting, supplier scoring, full analytics.
Their routers exist under `app/modules/{suppliers,inventory,packaging,delivery}`
as 501-returning placeholders so the module boundary is in place; `analytics`
exposes only the basic counts the MVP scope calls for.
