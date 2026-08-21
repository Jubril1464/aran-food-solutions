# Agric — Collective Agricultural Procurement Platform

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
- `backend/tests/test_lambda_handlers.py` — the serverless regression suite; drives
  the four Lambda entrypoints with synthetic API Gateway/SQS events in a
  subprocess, because the behaviour it guards is decided at *import* time from
  Lambda's environment. Re-run it after touching any of the handlers, the engine
  setup, the queue abstraction, the storage backend, the refresh cookie, or the
  seed data.
- `backend/tests/test_lambda_package.py` — guards the deployment artifact without
  needing AWS: pin drift between the two requirements files, a new third-party
  import that isn't packaged, and arq/redis becoming reachable from a handler's
  import graph. Cheap, and it fails at test time instead of on a cold start.
- `infra/scripts/build-lambda-package.py` — builds `infra/build/{layer,app}.zip`
  from any OS by having pip fetch Linux wheels; artifacts are byte-reproducible
  on purpose, so Terraform doesn't redeploy unchanged functions.
- `infra/` — Terraform for a fresh AWS account: **serverless** (four Lambda
  functions behind API Gateway + SQS, RDS Postgres, S3 + CloudFront), chosen
  deliberately over ECS Fargate for near-zero cost on a pitch-demo MVP — RDS is
  publicly reachable (accepted trade-off, avoids a NAT gateway) with a random
  password + server-side SSL enforcement, see `infra/DEPLOY.md`. Written and
  `terraform validate`-clean but **never applied**. Don't run
  `terraform apply`/`plan` against real credentials without the user explicitly
  asking for that specific action; writing/editing the `.tf` files is fine,
  provisioning billable infra is not a default action.

## Serverless invariants (backend runs on Lambda)

The API, notification worker, migration runner, and first-run bootstrap are
Lambda functions sharing one zip artifact + dependency layer, built by
`infra/scripts/build-lambda-package.py` (no Docker anywhere in the deploy); the
entrypoints are `app/lambda_handler.py`, `app/notification_worker_handler.py`,
`app/migration_handler.py`, and `app/seed_handler.py`. The same modules also run
as a normal uvicorn process locally, so keep these separations intact rather
than collapsing them:

- `app/core/queue.py` is the pluggable notification-queue abstraction keeping
  local dev on arq/Redis while `infra/` targets SQS — **don't collapse the two
  paths.** Same for `app/core/storage.py` (local disk vs S3).
- `app/core/database.py` switches to `NullPool` when `AWS_LAMBDA_FUNCTION_NAME`
  is set. Don't "restore" pooling there: each invocation gets a fresh event loop
  and a pooled asyncpg connection cannot cross that boundary. The Lambda
  concurrency caps in `infra/terraform` exist because that makes concurrency the
  database-connection count.
- Settings must never be named after a variable the Lambda runtime injects
  (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, …) — pydantic reads env vars
  case-insensitively and would capture the execution role's credentials without
  its session token. Hence `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY`; `aws_region`
  reads `AWS_REGION` on purpose, which is safe and correct.
- Anything the deployment needs from `backend/.env.example` also has to be set in
  `infra/terraform/lambda.tf` — Lambda never reads that file.
- `backend/requirements-lambda.txt` is the deployed subset of `requirements.txt`
  (no uvicorn/arq/redis/boto3/test deps). `tests/test_lambda_package.py` fails if
  a pin drifts between the two, if `app/` gains a third-party import that isn't
  packaged, or if anything a handler imports pulls in arq/redis at module scope —
  that last one is what makes excluding them safe, so keep those imports lazy.
- Notification delivery is at-least-once: `send_notification` raises so the
  consumer retries. Don't make it swallow exceptions "to stop the retries" —
  that silently drops notifications and empties the DLQ of its purpose.
- `/auth/register` creating only `CUSTOMER` is deliberate — don't add a role
  parameter or an admin-signup route. `app/seed_handler.py` is the one path to
  the first admin, and it must stay idempotent: it's a step people re-run.

## Known deliberate simplifications (see README "Architecture notes")

- Cycle-close only auto-advances an order if **all** its line items belong to the
  cycle being closed (orders spanning multiple open cycles are not split).
- Paystack runs in mock mode whenever `PAYSTACK_SECRET_KEY` is unset — useful for
  local dev/demo, but don't mistake mock-mode "success" for a real integration test.
