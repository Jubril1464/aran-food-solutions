resource "random_password" "db" {
  length  = 32
  special = false # avoid characters that need URL-encoding in the DATABASE_URL
}

locals {
  database_url = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${var.db_name}"
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}"
  subnet_ids = module.vpc.public_subnets # publicly accessible by design - see security_groups.tf

  tags = { Name = "${var.project_name}-${var.environment}" }
}

resource "aws_db_parameter_group" "postgres_force_ssl" {
  name   = "${var.project_name}-${var.environment}-force-ssl"
  family = "postgres16"

  # Server-side SSL enforcement (not just a client opting in) - since this
  # instance is publicly reachable, every connection is encrypted in transit.
  # Note: this encrypts the connection but does not verify the server's
  # certificate (that needs sslmode=verify-full + the RDS CA bundle) - see
  # infra/DEPLOY.md for the honest trade-off writeup.
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  tags = { Name = "${var.project_name}-${var.environment}-force-ssl" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-${var.environment}"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.postgres_force_ssl.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Deliberately public: no NAT/VPC-attached Lambda in this design (see
  # vpc.tf) - the accepted cost/security trade-off for a zero-traffic
  # pitch-demo MVP. Mitigated by a random 32-char password and
  # server-side-enforced SSL above. Do not point this at real customer data.
  publicly_accessible = true

  multi_az                  = var.db_multi_az
  backup_retention_period   = var.db_backup_retention_days
  deletion_protection       = var.db_deletion_protection
  skip_final_snapshot       = !var.db_deletion_protection
  final_snapshot_identifier = var.db_deletion_protection ? "${var.project_name}-${var.environment}-final" : null

  tags = { Name = "${var.project_name}-${var.environment}-postgres" }
}
