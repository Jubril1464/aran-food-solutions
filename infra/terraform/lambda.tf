locals {
  # Built by infra/scripts/build-lambda-package.py, which needs Python and a
  # network connection but no Docker. Terraform uploads these directly through
  # the Lambda API - there is no container registry in this design, and
  # therefore no "create the registry, push an image, then create the functions"
  # ordering problem: one `terraform apply` creates everything.
  #
  # filebase64sha256 fails loudly if an artifact is missing, which is the
  # intended behaviour: better a clear error at plan time than a deploy that
  # silently ships whatever was built last week.
  layer_zip = "${path.module}/../build/layer.zip"
  app_zip   = "${path.module}/../build/app.zip"

  common_environment = {
    ENVIRONMENT         = var.environment
    DATABASE_URL        = local.database_url
    DB_SSL_REQUIRED     = "true"
    STORAGE_BACKEND     = "s3"
    S3_BUCKET           = aws_s3_bucket.uploads.bucket
    S3_REGION           = var.aws_region
    EMAIL_BACKEND       = var.email_backend
    SMTP_HOST           = var.smtp_host
    SMTP_PORT           = tostring(var.smtp_port)
    SMTP_USERNAME       = var.smtp_username
    SMTP_PASSWORD       = var.smtp_password
    FRONTEND_URL        = "https://${aws_cloudfront_distribution.frontend.domain_name}"
    DELIVERY_FEE        = tostring(var.delivery_fee)
    SERVICE_FEE_PERCENT = tostring(var.service_fee_percent)
  }
}

# --- Dependencies, shared by all four functions ---
#
# A layer rather than four copies of the same 12 MB: the application code zip
# stays around 100 KB, so a code-only deploy re-uploads almost nothing, and the
# dependency tree is only re-uploaded when a pin actually changes.
#
# Layer versions are immutable. A rebuilt layer publishes a new version and the
# functions - which reference the versioned ARN below - pick it up on the same
# apply.
resource "aws_lambda_layer_version" "deps" {
  layer_name  = "${var.project_name}-${var.environment}-deps"
  description = "Python dependencies from backend/requirements-lambda.txt"

  filename         = local.layer_zip
  source_code_hash = filebase64sha256(local.layer_zip)

  compatible_runtimes      = [var.python_runtime]
  compatible_architectures = ["x86_64"]
}

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-api"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-${var.environment}-api"
  role          = aws_iam_role.lambda_api.arn

  runtime = var.python_runtime
  handler = "app.lambda_handler.handler"
  # Must match the wheels the build script downloads: the compiled dependencies
  # (asyncpg, pydantic-core) are x86_64 Linux binaries, so an arm64 function
  # would fail at import, not at deploy.
  architectures = ["x86_64"]

  filename         = local.app_zip
  source_code_hash = filebase64sha256(local.app_zip)
  layers           = [aws_lambda_layer_version.deps.arn]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout_api

  # Caps how many copies of this function can run at once, which - because the
  # engine uses a NullPool on Lambda (one fresh Postgres connection per
  # invocation, see app/core/database.py) - is also the cap on API database
  # connections. Unreserved, a traffic spike or a retry storm would scale to
  # the account's whole concurrency limit and exhaust db.t4g.micro's ~110
  # connections long before Lambda itself throttled. Set to -1 to opt out.
  reserved_concurrent_executions = var.lambda_api_reserved_concurrency

  environment {
    variables = merge(local.common_environment, {
      CORS_ORIGINS               = jsonencode(["https://${aws_cloudfront_distribution.frontend.domain_name}"])
      JWT_SECRET                 = random_password.jwt_secret.result
      PAYSTACK_SECRET_KEY        = var.paystack_secret_key
      QUEUE_BACKEND              = "sqs"
      SQS_NOTIFICATION_QUEUE_URL = aws_sqs_queue.notifications.url

      # The frontend (CloudFront) and this API (API Gateway) are different
      # sites, so the browser will not attach a SameSite=Lax refresh cookie to
      # an API call - silent token refresh would always 401. See
      # refresh_cookie_samesite in app/core/config.py.
      REFRESH_COOKIE_SAMESITE = "none"
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_api]
}

resource "aws_cloudwatch_log_group" "lambda_worker" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-worker"
  retention_in_days = 14
}

resource "aws_lambda_function" "worker" {
  function_name = "${var.project_name}-${var.environment}-worker"
  role          = aws_iam_role.lambda_worker.arn

  runtime       = var.python_runtime
  handler       = "app.notification_worker_handler.handler"
  architectures = ["x86_64"]

  filename         = local.app_zip
  source_code_hash = filebase64sha256(local.app_zip)
  layers           = [aws_lambda_layer_version.deps.arn]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout_worker

  environment {
    variables = local.common_environment
  }

  depends_on = [aws_cloudwatch_log_group.lambda_worker]
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

# --- Migration runner. Not on any request path and not scheduled: invoked by
# hand as a deploy step (infra/scripts/run-migrations.sh, or directly with
# `aws lambda invoke`). Costs nothing while idle, and runs `alembic upgrade
# head` from the exact artifact the API runs, rather than from whatever Python
# happens to be on the operator's machine. ---

resource "aws_cloudwatch_log_group" "lambda_migrate" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-migrate"
  retention_in_days = 14
}

resource "aws_lambda_function" "migrate" {
  function_name = "${var.project_name}-${var.environment}-migrate"
  role          = aws_iam_role.lambda_tasks.arn

  runtime       = var.python_runtime
  handler       = "app.migration_handler.handler"
  architectures = ["x86_64"]

  filename         = local.app_zip
  source_code_hash = filebase64sha256(local.app_zip)
  layers           = [aws_lambda_layer_version.deps.arn]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout_migrate

  # Two Alembic runs against one database at the same time (a double-click on
  # the deploy script, two people deploying at once) is a race worth making
  # impossible rather than unlikely. A second concurrent invoke is throttled
  # outright, which is the outcome we want here - fail fast, don't queue.
  reserved_concurrent_executions = 1

  environment {
    variables = local.common_environment
  }

  depends_on = [aws_cloudwatch_log_group.lambda_migrate]
}

# --- First-run bootstrap. /auth/register only ever creates customers, so a
# freshly deployed environment has no administrator and therefore no way to
# create products, categories or a procurement cycle. This creates the admin
# (and, by default, a starter catalogue with an open cycle) so the deployed site
# is demonstrable end to end. Invoked by hand, idempotent, free while idle. ---

resource "aws_cloudwatch_log_group" "lambda_seed" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-seed"
  retention_in_days = 14
}

resource "aws_lambda_function" "seed" {
  function_name = "${var.project_name}-${var.environment}-seed"
  role          = aws_iam_role.lambda_tasks.arn

  runtime       = var.python_runtime
  handler       = "app.seed_handler.handler"
  architectures = ["x86_64"]

  filename         = local.app_zip
  source_code_hash = filebase64sha256(local.app_zip)
  layers           = [aws_lambda_layer_version.deps.arn]

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout_migrate

  # Same reasoning as the migration function: two concurrent bootstraps racing
  # on unique constraints is a failure mode worth making impossible.
  reserved_concurrent_executions = 1

  environment {
    variables = merge(local.common_environment, {
      # Passed through the environment rather than an invoke payload so the
      # password never lands in shell history. Retrieve it with
      # `terraform output -raw admin_password`.
      SEED_ADMIN_EMAIL    = var.admin_email
      SEED_ADMIN_PASSWORD = local.admin_password
      SEED_DEMO_DATA      = tostring(var.seed_demo_data)
    })
  }

  depends_on = [aws_cloudwatch_log_group.lambda_seed]
}

locals {
  # Generated unless one was supplied, so a first deploy needs no secret invented
  # up front and no password reused from somewhere else.
  admin_password = var.admin_password != "" ? var.admin_password : random_password.admin.result
}

resource "random_password" "admin" {
  length = 24
  # Excludes quotes/backslashes and other characters that turn into a shell or
  # JSON escaping problem when the password is copied around by hand.
  override_special = "!#%*+-=?_"
}
