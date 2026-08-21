variable "aws_region" {
  description = "AWS region to create the state bucket/lock table in. Should match the region used by infra/terraform."
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short name used to prefix resource names (bucket, table)."
  type        = string
  default     = "agric"
}
