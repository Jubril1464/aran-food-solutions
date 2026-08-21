output "aws_region" {
  value = var.aws_region
}

output "api_invoke_url" {
  description = "HTTPS URL for the backend API (API Gateway's own endpoint - no CloudFront/ALB in front of it). Use this + /api/v1 as VITE_API_BASE_URL when building the frontend."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "frontend_url" {
  description = "Public HTTPS URL for the React app."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_bucket_name" {
  description = "Sync the built frontend here (scripts/deploy-frontend.sh)."
  value       = aws_s3_bucket.frontend.bucket
}

output "frontend_cloudfront_distribution_id" {
  description = "Needed to invalidate the CloudFront cache after a frontend deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "uploads_bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}

output "database_url" {
  description = "Full DATABASE_URL, so migrations can be run locally against the public RDS endpoint (scripts/run-migrations.sh) - RDS is publicly reachable in this design, no bastion/run-task needed."
  value       = local.database_url
  sensitive   = true
}

output "rds_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}

output "notifications_queue_url" {
  value = aws_sqs_queue.notifications.url
}

output "migrate_function_name" {
  description = "Migration runner. Apply migrations with: aws lambda invoke --function-name <this> --cli-binary-format raw-in-base64-out /dev/stdout (or use infra/scripts/run-migrations.sh)."
  value       = aws_lambda_function.migrate.function_name
}

output "seed_function_name" {
  description = "First-run bootstrap. Creates the admin account (and starter catalogue) with: aws lambda invoke --function-name <this> /dev/stdout"
  value       = aws_lambda_function.seed.function_name
}

output "admin_email" {
  description = "Login for the admin UI, created by the seed function."
  value       = var.admin_email
}

output "admin_password" {
  description = "Password for that admin login (generated unless you supplied one). Read with: terraform output -raw admin_password"
  value       = local.admin_password
  sensitive   = true
}
