resource "aws_kms_key" "app" {

  description             = "${local.name} encrypted retained resources"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "app" {

  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.app.key_id
}

resource "aws_db_subnet_group" "app" {

  name       = local.name
  subnet_ids = aws_subnet.database[*].id
}

resource "aws_db_instance" "app" {

  identifier                      = local.name
  engine                          = "postgres"
  engine_version                  = "17.9"
  instance_class                  = "db.t4g.micro"
  db_name                         = "planner"
  username                        = "planner_admin"
  manage_master_user_password     = true
  master_user_secret_kms_key_id   = aws_kms_key.app.arn
  allocated_storage               = 20
  max_allocated_storage           = 30
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.app.arn
  publicly_accessible             = false
  multi_az                        = false
  db_subnet_group_name            = aws_db_subnet_group.app.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  backup_retention_period         = 7
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-final-retained"
  copy_tags_to_snapshot           = true
  auto_minor_version_upgrade      = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

}

resource "random_password" "application" {

  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "application" {

  name                    = "${local.name}/application-db"
  kms_key_id              = aws_kms_key.app.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "application" {

  secret_id     = aws_secretsmanager_secret.application.id
  secret_string = jsonencode({ password = random_password.application.result })

}

resource "aws_s3_bucket" "artifacts" {

  bucket_prefix = "${local.name}-artifacts-"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "artifacts" {

  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {

  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {

    status = "Enabled"
  }

}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {

  bucket = aws_s3_bucket.artifacts.id
  rule {

    apply_server_side_encryption_by_default {

      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.app.arn
    }

    bucket_key_enabled = true
  }

}

resource "aws_s3_bucket_policy" "tls" {

  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }] })
}

resource "aws_ecr_repository" "app" {

  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration {

    scan_on_push = true
  }

  encryption_configuration {

    encryption_type = "KMS"
    kms_key         = aws_kms_key.app.arn
  }

}

resource "aws_ecr_lifecycle_policy" "app" {

  repository = aws_ecr_repository.app.name
  policy     = jsonencode({ rules = [{ rulePriority = 1, description = "Retain ten images for rollback", selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }, action = { type = "expire" } }] })
}

resource "aws_cognito_user_pool" "app" {
  user_pool_tier = "ESSENTIALS"

  name = local.name
  admin_create_user_config {

    allow_admin_create_user_only = true
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "ACTIVE"
  password_policy {

    minimum_length    = 14
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }


}

resource "aws_cognito_user_pool_domain" "app" {

  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.app.id
}

resource "aws_cognito_user_pool_client" "web" {

  name                                 = "planner-web"
  user_pool_id                         = aws_cognito_user_pool.app.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = ["${var.application_origin}/api/v1/auth/callback"]
  logout_urls                          = [var.application_origin]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true

}

