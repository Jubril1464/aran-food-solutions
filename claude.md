# Aran Food Solutions — Collective Agricultural Procurement Platform

MVP for a Nigerian collective procurement platform: customers order commodities,
orders pool into time-boxed procurement cycles, admin closes a cycle to trigger
bulk aggregation. Full context, stack, run/test instructions: see [README.md](README.md).
Original product spec: `Collective_Agricultural_Procurement_PRD.docx`.

## Scope discipline

This build is intentionally split into two priorities — **Customer flow, then
Admin flow** — with Suppliers/Inventory/Packaging/Delivery/Forecasting/full
Analytics explicitly deferred to a later Operations phase. Their module folders
under `backend/app/modules/` exist as 501-returning placeholder routers only —
**do not add real tables or logic there** without the user first confirming the
phase has changed; that boundary was a deliberate, explicit scope decision.

## Layout

- `backend/` — FastAPI modular monolith, SQLAlchemy 2.0 async, Alembic, arq worker.
  One folder per domain under `app/modules/`; models under `app/models/`; the order
  state machine (`ALLOWED_TRANSITIONS`) lives in `app/models/order.py`.
- `frontend/` — Vite + React + TypeScript + Tailwind. `src/api/` wraps every backend
  endpoint; `src/context/AuthContext.tsx` holds the JWT access token in memory and
  silently refreshes it from the httpOnly cookie on load.
- `backend/tests/test_flow.py` — the primary regression suite; runs on SQLite with
  a mocked notification queue, no live Postgres/Redis needed. Re-run this after
  touching checkout, payments, or procurement-cycle logic — it's what caught the
  cart identity-map staleness, decimal-quantization, and naive/aware-datetime bugs
  during the initial build.
- `backend/tests/test_deployment.py` — guards the hosting-specific pieces:
  managed-Postgres URL normalisation, in-process notification delivery (the path
  the rest of the suite mocks out), the startup sweep of PENDING notifications,
  and that the seeded admin can actually log in. Re-run it after touching
  `app/core/queue.py`, `app/core/database.py`, or the seed defaults.
- `render.yaml` + `backend/start.sh` — the entire deployment. Render creates both
  services from the blueprint; `start.sh` runs migrations and the seed on every
  boot (both idempotent) because a free tier has no one-off jobs or shell.
- `DEPLOY.md` — the runbook, including the free-tier limits that actually bite.

## Deployment invariants

Hosted on Render (native Python web service + static site) with Neon Postgres.
**Deliberately no Docker and no AWS**: the user could not complete AWS payment
verification, so the previous Terraform/Lambda deployment was removed — it is
still in git history (`git log -- infra/`) if that ever changes. Don't
reintroduce a container-based deploy path without being asked.

- Notification transport is pluggable (`app/core/queue.py`): `in_process` (an
  asyncio task, the hosted default — no Redis, no second service, which is what
  makes one free instance enough) and `redis` (arq + a worker process, used by
  `docker-compose.yml`). **Keep both paths working.** Requests must never wait on
  delivery, whichever is selected.
- `redeliver_pending()` runs at startup because an in-process task dies with its
  process and free instances are stopped when idle. Without it, anything enqueued
  just before a restart is lost.
- `normalize_database_url()` in `app/core/database.py` is what lets a Neon/Supabase
  connection string be pasted verbatim: it rewrites the scheme for asyncpg and
  strips libpq-only parameters (`sslmode`, `channel_binding`) that would otherwise
  raise a TypeError on the first query. Don't "simplify" it away.
- The refresh cookie must stay `SameSite=None; Secure` in the hosted config: the
  frontend and API are on different hostnames, so a Lax cookie is never sent and
  silent refresh breaks on every page load.
- `SEED_ADMIN_EMAIL` must never default to a `.local`/`.test` address. The seed
  writes straight through the model, but login validates with `EmailStr`, which
  rejects RFC 6761 special-use names — producing an admin that exists and cannot
  authenticate. There is a regression test for exactly this.
- Anything the deployment needs from `backend/.env.example` also has to be added
  to `render.yaml` — Render never reads that file.
- `/auth/register` creating only `CUSTOMER` is deliberate — don't add a role
  parameter or an admin-signup route. `app/seed.py` is the one path to the first
  admin, and it must stay idempotent: `start.sh` runs it on every boot.

## Known deliberate simplifications (see README "Architecture notes")

- Cycle-close only auto-advances an order if **all** its line items belong to the
  cycle being closed (orders spanning multiple open cycles are not split).
- Paystack runs in mock mode whenever `PAYSTACK_SECRET_KEY` is unset — useful for
  local dev/demo, but don't mistake mock-mode "success" for a real integration test.
