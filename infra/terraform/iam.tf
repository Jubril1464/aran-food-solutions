data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# --- API function: basic execution (CloudWatch Logs) + S3 read/write scoped
# to the uploads bucket only. Not VPC-attached, so no
# AWSLambdaVPCAccessExecutionRole is needed. ---

resource "aws_iam_role" "lambda_api" {
  name               = "${var.project_name}-${var.environment}-lambda-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_api_basic" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_api_s3" {
  statement {
    sid       = "ListUploadsBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.uploads.arn]
  }
  statement {
    sid       = "ReadWriteUploadedObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
}

resource "aws_iam_role_policy" "lambda_api_s3" {
  name   = "uploads-bucket-access"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.lambda_api_s3.json
}

# The API function is the *producer* on the notifications queue: every
# register / checkout / payment-verify / cycle-close request persists a
# Notification row and enqueues its id (app/core/queue.py, QUEUE_BACKEND=sqs).
# Without sqs:SendMessage those requests fail with an AccessDenied from boto3,
# so this is load-bearing, not defensive.
data "aws_iam_policy_document" "lambda_api_sqs" {
  statement {
    sid       = "EnqueueNotifications"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.notifications.arn]
  }
}

resource "aws_iam_role_policy" "lambda_api_sqs" {
  name   = "enqueue-notifications"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.lambda_api_sqs.json
}

# --- Worker function: basic execution + permission to consume the
# notifications SQS queue. ---

resource "aws_iam_role" "lambda_worker" {
  name               = "${var.project_name}-${var.environment}-lambda-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_worker_basic" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_worker_sqs" {
  statement {
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.notifications.arn]
  }
}

resource "aws_iam_role_policy" "lambda_worker_sqs" {
  name   = "consume-notifications-queue"
  role   = aws_iam_role.lambda_worker.id
  policy = data.aws_iam_policy_document.lambda_worker_sqs.json
}

# --- Manually-invoked task functions (migrate, seed): basic execution only.
# They talk to RDS over its public endpoint (see rds.tf) and need no S3, SQS or
# VPC access. Shared because their permission needs are identical - splitting
# them would grant neither of them anything it doesn't already have. ---

resource "aws_iam_role" "lambda_tasks" {
  name               = "${var.project_name}-${var.environment}-lambda-tasks"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_tasks_basic" {
  role       = aws_iam_role.lambda_tasks.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
