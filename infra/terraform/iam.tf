locals {

  ecs_assume = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })

}

resource "aws_iam_role" "execution" {

  name               = "${local.name}-execution"
  assume_role_policy = local.ecs_assume
}

resource "aws_iam_role_policy_attachment" "execution" {

  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secrets" {

  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_secretsmanager_secret.application.arn, aws_db_instance.app.master_user_secret[0].secret_arn] },
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = [aws_kms_key.app.arn] }
  ] })
}

resource "aws_iam_role" "task" {

  name               = "${local.name}-task"
  assume_role_policy = local.ecs_assume
}

resource "aws_iam_role_policy" "telemetry" {

  role = aws_iam_role.task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"], Resource = "*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"], Resource = "${aws_cloudwatch_log_group.telemetry.arn}:*" },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.artifacts.arn}/releases/*" },
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = aws_kms_key.app.arn }
  ] })
}

resource "aws_iam_openid_connect_provider" "github" {

  count          = var.github_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

}

locals {

  github_oidc_arn = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn

}

resource "aws_iam_role" "release" {

  name               = "${local.name}-release"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Federated = local.github_oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity", Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com", "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:environment:release" } } }] })
}

resource "aws_iam_role_policy" "release" {

  role = aws_iam_role.release.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken", "ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition", "ecs:ListTasks", "ecs:DescribeTasks"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"], Resource = aws_ecr_repository.app.arn },
    { Effect = "Allow", Action = ["ecs:DescribeServices", "ecs:UpdateService"], Resource = [for service in aws_ecs_service.app : service.id] },
    { Effect = "Allow", Action = ["ecs:RunTask"], Resource = "arn:aws:ecs:${var.region}:${data.aws_caller_identity.current.account_id}:task-definition/${local.name}-*:*", Condition = { ArnEquals = { "ecs:cluster" = aws_ecs_cluster.app.arn } } },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.execution.arn, aws_iam_role.task.arn], Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } } }
  ] })
}

