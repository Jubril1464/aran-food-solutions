resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${var.project_name}-${var.environment}-notifications-dlq"
  message_retention_seconds = 1209600 # 14 days - time to notice/investigate a failed notification

  tags = { Name = "${var.project_name}-${var.environment}-notifications-dlq" }
}

resource "aws_sqs_queue" "notifications" {
  name = "${var.project_name}-${var.environment}-notifications"

  # Must exceed the worker Lambda's timeout (AWS recommends 6x) so a message
  # can't become visible to a second consumer while still being processed.
  visibility_timeout_seconds = var.lambda_timeout_worker * 6

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.project_name}-${var.environment}-notifications" }
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = aws_sqs_queue.notifications.arn
  function_name    = aws_lambda_function.worker.arn

  # The handler processes a batch one message at a time and reports failures
  # per message, so a batch larger than 1 amortises cold starts without
  # coupling messages together. With no batching window, SQS still delivers
  # however few messages are actually available - this adds no latency at
  # demo volume. Kept well under what the worker's timeout allows: a batch that
  # runs out of time is redelivered whole (a timeout can't report per-message
  # failures), which idempotent delivery absorbs but shouldn't have to.
  batch_size = 5

  # Without this, a single failed message makes SQS redeliver the *whole*
  # batch, re-sending notifications that already went out.
  # app/notification_worker_handler.py returns {"batchItemFailures": [...]} to
  # match, and only those come back.
  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    # Same reasoning as the API function's reserved concurrency: each concurrent
    # worker holds its own Postgres connection (NullPool on Lambda), and a
    # backlog would otherwise let SQS scale this out aggressively enough to
    # exhaust db.t4g.micro's connection limit. AWS requires >= 2.
    maximum_concurrency = var.worker_max_concurrency
  }
}
