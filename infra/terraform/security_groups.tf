resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds"
  description = "Postgres: publicly reachable (Lambda has no stable outbound IP to scope this to)"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Postgres from anywhere - accepted trade-off for a zero-cost/no-NAT pitch-demo MVP, mitigated by a random password + server-side-enforced SSL (see rds.tf)"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-${var.environment}-rds" }
}
