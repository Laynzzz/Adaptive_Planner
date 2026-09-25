mock_provider "aws" {
  mock_data "aws_availability_zones" { defaults = { names = ["us-east-1a", "us-east-1b"] } }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012" } }
}
mock_provider "random" {}
variables {
  owner_tag             = "synthetic-review"
  cost_center           = "synthetic-review"
  application_origin    = "https://planner.example.com"
  certificate_arn       = "arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
  cognito_domain_prefix = "synthetic-planner-review"
  image                 = "123456789012.dkr.ecr.us-east-1.amazonaws.com/planner@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  budget_usd            = 300
  budget_email          = "synthetic@example.com"
  github_repository     = "synthetic/planner"
}
run "reference_safety_boundaries" {
  command = plan
  assert {
    condition     = aws_db_instance.app.publicly_accessible == false && aws_db_instance.app.storage_encrypted && aws_db_instance.app.deletion_protection
    error_message = "RDS must stay private, encrypted and protected from accidental deletion."
  }
  assert {
    condition     = alltrue([for service in aws_ecs_service.app : service.desired_count == 0 && service.deployment_circuit_breaker[0].enable && service.deployment_circuit_breaker[0].rollback])
    error_message = "Bootstrap starts no tasks and each future service requires circuit-breaker rollback."
  }
  assert {
    condition     = aws_ecr_repository.app.image_tag_mutability == "IMMUTABLE" && aws_s3_bucket.artifacts.force_destroy == false
    error_message = "Images and retained artifacts must not silently be overwritten or destroyed."
  }
}
