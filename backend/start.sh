#!/usr/bin/env sh
# Start command for the hosted API service (see ../render.yaml).
#
# Three steps, in order, every time the service boots: apply migrations, ensure
# an administrator exists, then serve. Migrations and seeding are both
# idempotent, so running them on every boot is safe - and it means a deploy needs
# no separate one-off command, which matters on a free tier where one-off jobs
# and shell access aren't available.
set -e

echo "==> Applying database migrations"
python -m alembic upgrade head

# Skipped rather than failed when unconfigured: an app that boots without an
# admin is recoverable (set the variable and redeploy), whereas a service that
# refuses to start is a harder thing to diagnose from a deploy log.
if [ -n "$SEED_ADMIN_PASSWORD" ]; then
  echo "==> Ensuring admin account and starter data exist"
  python -m app.seed
else
  echo "==> SEED_ADMIN_PASSWORD is not set; skipping bootstrap."
  echo "    Without it there is no admin account, so the admin UI cannot be used."
fi

# exec so uvicorn replaces this shell as PID 1 and receives SIGTERM directly -
# otherwise the platform's shutdown signal goes to the shell and the server is
# killed rather than being allowed to finish in-flight requests.
echo "==> Starting API on port ${PORT:-8000}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
