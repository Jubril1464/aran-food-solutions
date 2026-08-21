# Bucket/table/region/key are intentionally NOT hardcoded here — they come from
# infra/bootstrap's outputs, passed at `terraform init` time so this file never
# needs editing:
#
#   terraform init \
#     -backend-config="bucket=<state_bucket_name from bootstrap output>" \
#     -backend-config="dynamodb_table=<lock_table_name from bootstrap output>" \
#     -backend-config="region=<aws_region>"
#
# See ../../DEPLOY.md for the full first-time sequence.

terraform {
  backend "s3" {
    key     = "agric/prod/terraform.tfstate"
    encrypt = true
  }
}
