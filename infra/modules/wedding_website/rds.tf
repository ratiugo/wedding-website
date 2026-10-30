resource "aws_db_subnet_group" "main" {
  name       = "wedding-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_rds_cluster" "main" {
  cluster_identifier = "wedding-${var.environment}"
  engine             = "aurora-postgresql"
  engine_version     = "17.11"
  database_name      = "wedding"
  master_username             = "wedding_admin"
  manage_master_user_password = true
  iam_database_authentication_enabled = true
  enable_http_endpoint = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  storage_encrypted      = true

  backup_retention_period   = 7
  deletion_protection       = true
  final_snapshot_identifier = "wedding-${var.environment}-final"

  serverlessv2_scaling_configuration {
    min_capacity             = 0
    max_capacity             = 1
    seconds_until_auto_pause = 300
  }
}

resource "aws_rds_cluster_instance" "main" {
  identifier         = "wedding-${var.environment}-1"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
}
