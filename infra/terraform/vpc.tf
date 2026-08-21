data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs            = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)
  public_subnets = [for i in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 4, i)]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${var.project_name}-${var.environment}"
  cidr = var.vpc_cidr

  azs            = local.azs
  public_subnets = local.public_subnets

  # Public subnets only, no NAT gateway: nothing in this design needs one.
  # Lambda isn't VPC-attached (direct internet egress by default), and RDS is
  # deliberately publicly accessible (see rds.tf / security_groups.tf) rather
  # than sitting in a NAT-routed private subnet — the cost/security trade-off
  # explicitly chosen for a zero-traffic pitch-demo MVP. Revisit if this ever
  # needs to handle real customer data at real traffic.
  enable_nat_gateway = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}
