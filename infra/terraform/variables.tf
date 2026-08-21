variable "aws_region" {
  description = "AWS region for all resources. Must match the region used in infra/bootstrap."
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short name used to prefix/tag resources."
  type        = string
  default     = "agric"
}

variable "environment" {
  description = "Environment name (used in tags and resource names)."
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to spread the (public-only) subnets across. RDS requires a subnet group spanning at least 2 AZs even for a single-AZ instance."
  type        = number
  default     = 2
}

# --- Database ---

variable "db_instance_class" {
  description = "RDS instance class. db.t4g.micro is free-tier eligible on a new AWS account (check your account's actual Free Tier status/expiry) and the cheapest Graviton burstable tier otherwise."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "agric"
}

variable "db_username" {
  type    = string
  default = "agric_app"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ RDS failover. Off by default (cost + not needed for a demo)."
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_deletion_protection" {
  description = "Off for MVP so the environment can be torn down easily. Turn on before this ever holds real customer data."
  type        = bool
  default     = false
}

# --- Lambda sizing ---

variable "lambda_memory_size" {
  description = "Memory (MB) for both the API and worker functions. Also determines proportional CPU."
  type        = number
  default     = 512
}

variable "lambda_timeout_api" {
  description = "API function timeout (seconds). API Gateway itself has a hard 30s cap, so this can't usefully exceed that."
  type        = number
  default     = 29
}

variable "lambda_timeout_worker" {
  description = "Notification worker timeout (seconds) - generous for occasional slow SMTP sends."
  type        = number
  default     = 60
}

variable "lambda_timeout_migrate" {
  description = "Migration function timeout (seconds). Not behind API Gateway, so it isn't bound by the 30s API limit - Alembic on a cold start plus a table-rewriting migration can legitimately take minutes."
  type        = number
  default     = 300
}

variable "lambda_api_reserved_concurrency" {
  description = "Max concurrent API function executions, which is also the cap on API->Postgres connections (the Lambda engine uses a NullPool: one connection per invocation). db.t4g.micro allows roughly 110 total. Set to -1 to remove the reservation - do that if `terraform apply` reports a concurrency-limit error, which means the account's per-region limit is lower than this value."
  type        = number
  default     = 20
}

variable "worker_max_concurrency" {
  description = "Max concurrent notification-worker executions fanned out by the SQS event source mapping. Same database-connection reasoning as lambda_api_reserved_concurrency. AWS requires >= 2."
  type        = number
  default     = 5

  validation {
    condition     = var.worker_max_concurrency >= 2
    error_message = "SQS event source mapping maximum_concurrency must be at least 2."
  }
}

variable "python_runtime" {
  description = "Lambda Python runtime. Must match TARGET_PYTHON in infra/scripts/build-lambda-package.py: the compiled dependencies are built for one exact CPython version (asyncpg ships a cp312 .so, not an abi3 wheel), so a mismatch fails at import rather than at deploy."
  type        = string
  default     = "python3.12"
}

# --- App configuration / secrets ---
#
# No Secrets Manager in this design (dropped deliberately - see infra/DEPLOY.md):
# these are set directly as Lambda environment variables (KMS-encrypted at
# rest by default), which is simpler and, for this project's threat model,
# not meaningfully less safe than the extra indirection.

variable "paystack_secret_key" {
  description = "Paystack secret key. Leave blank to run the app in its built-in Paystack mock mode (safe default for first deploy)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "email_backend" {
  description = "\"console\" (logs instead of sending, safe default) or \"smtp\"."
  type        = string
  default     = "console"
}

variable "smtp_host" {
  type      = string
  default   = ""
  sensitive = true
}

variable "smtp_port" {
  type    = number
  default = 587
}

variable "smtp_username" {
  type      = string
  default   = ""
  sensitive = true
}

variable "smtp_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "delivery_fee" {
  type    = number
  default = 1000.0
}

variable "service_fee_percent" {
  type    = number
  default = 2.5
}

# --- First-admin bootstrap (consumed by the seed function) ---

variable "admin_email" {
  description = "Email for the platform administrator account created by the seed function. This is the login for the admin UI."
  type        = string
  default     = "admin@agric.local"
}

variable "admin_password" {
  description = "Password for that account. Leave blank to have one generated - read it afterwards with `terraform output -raw admin_password`."
  type        = string
  default     = ""
  sensitive   = true
}

variable "seed_demo_data" {
  description = "Whether the seed function also creates a starter catalogue (categories, products) and an open procurement cycle per category. Needed for the deployed site to demo end to end; set false if you want an empty platform."
  type        = bool
  default     = true
}
