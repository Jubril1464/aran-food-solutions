#!/usr/bin/env bash
# Builds the frontend against the live API Gateway URL, uploads it to the
# frontend S3 bucket, and invalidates the CloudFront cache so the new build
# is served immediately instead of waiting out the old cache TTL.
#
# Run this after `terraform apply` has created (or updated) the API Gateway
# stage / frontend CloudFront distribution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/infra/terraform"
FRONTEND_DIR="$REPO_ROOT/frontend"

API_URL="$(terraform -chdir="$TF_DIR" output -raw api_invoke_url)"
API_URL="${API_URL%/}" # the $default stage's invoke_url has a trailing slash
BUCKET="$(terraform -chdir="$TF_DIR" output -raw frontend_bucket_name)"
DISTRIBUTION_ID="$(terraform -chdir="$TF_DIR" output -raw frontend_cloudfront_distribution_id)"

echo "==> Building frontend with VITE_API_BASE_URL=${API_URL}/api/v1 ..."
(
  cd "$FRONTEND_DIR"
  VITE_API_BASE_URL="${API_URL}/api/v1" npm run build
)

echo "==> Syncing dist/ to s3://$BUCKET ..."
aws s3 sync "$FRONTEND_DIR/dist" "s3://$BUCKET" --delete

echo "==> Invalidating CloudFront cache ($DISTRIBUTION_ID) ..."
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" >/dev/null

echo "==> Done. Frontend live at: $(terraform -chdir="$TF_DIR" output -raw frontend_url)"
