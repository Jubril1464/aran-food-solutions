output "state_bucket_name" {
  description = "Pass this to `terraform init -backend-config=bucket=...` in infra/terraform."
  value       = aws_s3_bucket.tf_state.bucket
}

output "lock_table_name" {
  description = "Pass this to `terraform init -backend-config=dynamodb_table=...` in infra/terraform."
  value       = aws_dynamodb_table.tf_lock.name
}

output "aws_region" {
  value = var.aws_region
}
