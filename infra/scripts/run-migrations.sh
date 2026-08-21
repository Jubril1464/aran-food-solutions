#!/usr/bin/env bash
# Applies `alembic upgrade head` to the deployed database.
#
# Default path: invoke the migration Lambda (infra/terraform/lambda.tf), which
# runs Alembic from the exact same artifact and layer the API runs. Nothing is
# needed locally beyond Terraform and the AWS CLI - no Python, no venv, and no
# direct database reachability from your machine.
#
# Fallback path (--local): run Alembic on this machine against the public RDS
# endpoint. Needs Python 3.12 + backend/requirements.txt installed. Kept
# because it's useful when iterating on a migration, and because it's the only
# option if the deployed artifact is older than the revision you want to apply.
#
# Run this after every deploy that includes a new Alembic revision.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/infra/terraform"
BACKEND_DIR="$REPO_ROOT/backend"

if [[ "${1:-}" == "--local" ]]; then
  echo "==> Running migrations locally against the deployed RDS endpoint..."
  DATABASE_URL="$(terraform -chdir="$TF_DIR" output -raw database_url)"
  (
    cd "$BACKEND_DIR"
    DATABASE_URL="$DATABASE_URL" DB_SSL_REQUIRED=true JWT_SECRET=unused-for-migrations python -m alembic upgrade head
  )
  echo "==> Migrations applied successfully."
  exit 0
fi

FUNCTION_NAME="$(terraform -chdir="$TF_DIR" output -raw migrate_function_name)"
REGION="$(terraform -chdir="$TF_DIR" output -raw aws_region)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT

echo "==> Invoking $FUNCTION_NAME (alembic upgrade head)..."
# --cli-binary-format raw-in-base64-out: without it AWS CLI v2 expects --payload
# to already be base64. --log-type Tail returns the function's own log output, so
# a failed migration is diagnosable right here rather than only in CloudWatch.
# FunctionError comes back as the literal "None" when the function succeeded.
INVOKE_OUTPUT="$(
  aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --cli-binary-format raw-in-base64-out \
    --payload '{}' \
    --log-type Tail \
    --query '[FunctionError, LogResult]' \
    --output text \
    "$RESPONSE_FILE"
)"

FUNCTION_ERROR="$(printf '%s' "$INVOKE_OUTPUT" | cut -f1)"
LOG_TAIL_B64="$(printf '%s' "$INVOKE_OUTPUT" | cut -f2)"

echo "--- function log ---"
printf '%s' "$LOG_TAIL_B64" | base64 --decode 2>/dev/null ||
  printf '%s' "$LOG_TAIL_B64" | base64 -D 2>/dev/null ||
  printf '%s' "$LOG_TAIL_B64" | openssl base64 -d -A 2>/dev/null ||
  echo "(couldn't decode the log tail here - see CloudWatch: /aws/lambda/$FUNCTION_NAME)"
echo "--------------------"

# An unhandled exception inside the function is still a *successful invocation*
# as far as the Lambda API is concerned (HTTP 200 plus a FunctionError field),
# so the exit status alone would report a failed migration as a success.
if [[ "$FUNCTION_ERROR" != "None" ]]; then
  echo "==> Migration FAILED ($FUNCTION_ERROR). Response payload:" >&2
  cat "$RESPONSE_FILE" >&2
  echo >&2
  exit 1
fi

echo "==> Migrations applied successfully: $(cat "$RESPONSE_FILE")"
