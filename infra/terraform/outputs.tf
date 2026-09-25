output "application_url" {

  value = var.application_origin
}

output "alb_dns_name" {

  value = aws_lb.app.dns_name
}

output "cluster" {

  value = aws_ecs_cluster.app.name
}

output "services" {

  value = { for key, service in aws_ecs_service.app : key => service.name }
}

output "migration_task" {

  value = aws_ecs_task_definition.migrate.arn
}

output "subnets" {

  value = aws_subnet.public[*].id
}

output "task_security_group" {

  value = aws_security_group.task.id
}

output "ecr_url" {

  value = aws_ecr_repository.app.repository_url
}

output "artifact_bucket" {

  value = aws_s3_bucket.artifacts.id
}

output "release_role_arn" {

  value = aws_iam_role.release.arn
}

output "retained_inventory" {

  value = { database = aws_db_instance.app.identifier, final_snapshot = aws_db_instance.app.final_snapshot_identifier, artifact_bucket = aws_s3_bucket.artifacts.id, ecr_repository = aws_ecr_repository.app.name, kms_key = aws_kms_key.app.arn, db_secret = aws_secretsmanager_secret.application.arn, user_pool = aws_cognito_user_pool.app.id }
}

