resource "aws_cloudwatch_log_group" "app" {

  name              = "/${local.name}/application"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "telemetry" {

  name              = "/${local.name}/metrics"
  retention_in_days = 7
}

resource "aws_ecs_cluster" "app" {

  name = local.name
  setting {

    name  = "containerInsights"
    value = "disabled"
  }

}

locals {

  services = {
    api            = { cpu = 512, memory = 1024, command = ["python", "-m", "planner.cli", "serve", "--host", "0.0.0.0", "--port", "8000"] }
    solve          = { cpu = 2048, memory = 4096, command = ["python", "-m", "planner.jobs.worker"] }
    interpretation = { cpu = 256, memory = 1024, command = ["python", "-m", "planner.ai.worker"] }
    calendar       = { cpu = 256, memory = 1024, command = ["python", "-m", "planner.calendar.worker"] }
  }
  environment = [
    { name = "PLANNER_ENVIRONMENT", value = "cloud" },
    { name = "PLANNER_APP_ORIGIN", value = var.application_origin },
    { name = "PLANNER_UI_ORIGIN", value = var.application_origin },
    { name = "PLANNER_OIDC_ISSUER", value = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.app.id}" },
    { name = "PLANNER_OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.web.id },
    { name = "PLANNER_DATABASE_HOST", value = aws_db_instance.app.address },
    { name = "PLANNER_DATABASE_USERNAME", value = "planner_app" },
    { name = "PLANNER_DATABASE_NAME", value = "planner" },
    { name = "PLANNER_DATABASE_SSLMODE", value = "require" },
    { name = "PLANNER_OTLP_ENDPOINT", value = "http://127.0.0.1:4318" },
    { name = "PLANNER_TRACE_SAMPLE_RATIO", value = "0.1" },
    { name = "PLANNER_AI_LIVE_ENABLED", value = "false" },
    { name = "PLANNER_CALENDAR_LIVE_ENABLED", value = "false" },
    { name = "PLANNER_ROUTING_MODE", value = "fixed" }
  ]
  logging   = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.app.name, "awslogs-region" = var.region, "awslogs-stream-prefix" = "planner" } }
  collector = { name = "otel", image = var.collector_image, essential = false, memoryReservation = 128, command = ["--config=env:OTEL_CONFIG"], environment = [{ name = "OTEL_CONFIG", value = file("${path.module}/../observability/aws.yaml") }, { name = "AWS_REGION", value = var.region }, { name = "PLANNER_METRIC_LOG_GROUP", value = aws_cloudwatch_log_group.telemetry.name }], logConfiguration = local.logging }

}

resource "aws_ecs_task_definition" "app" {

  for_each                 = local.services
  family                   = "${local.name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {

    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    { name         = "planner", image = var.image, essential = true, user = "10001:10001", readonlyRootFilesystem = true, command = each.value.command,
      environment  = concat(local.environment, [{ name = "PLANNER_SERVICE_NAME", value = "planner-${each.key}" }]),
      secrets      = [{ name = "PLANNER_DATABASE_PASSWORD", valueFrom = "${aws_secretsmanager_secret.application.arn}:password::" }],
      portMappings = each.key == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : [],
      mountPoints  = [{ sourceVolume = "scratch", containerPath = "/tmp", readOnly = false }],
    dependsOn = [{ containerName = "scratch-init", condition = "SUCCESS" }], stopTimeout = 30, logConfiguration = local.logging },
    { name    = "scratch-init", image = var.image, essential = false, user = "0:0", readonlyRootFilesystem = true,
      command = ["python", "-c", "import os; os.chmod('/scratch', 0o1777)"],
    mountPoints = [{ sourceVolume = "scratch", containerPath = "/scratch", readOnly = false }], logConfiguration = local.logging },
  local.collector])
  volume {

    name = "scratch"
  }


}

resource "aws_ecs_service" "app" {

  for_each                           = local.services
  name                               = "${local.name}-${each.key}"
  cluster                            = aws_ecs_cluster.app.id
  task_definition                    = aws_ecs_task_definition.app[each.key].arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "1.4.0"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {

    enable   = true
    rollback = true
  }

  network_configuration {

    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  dynamic "load_balancer" {

    for_each = each.key == "api" ? [1] : []
    content {

      target_group_arn = aws_lb_target_group.api.arn
      container_name   = "planner"
      container_port   = 8000
    }

  }

  health_check_grace_period_seconds = each.key == "api" ? 60 : null
  depends_on                        = [aws_lb_listener.https]
  lifecycle {

    ignore_changes = [task_definition]
  }


}

resource "aws_ecs_task_definition" "migrate" {

  family                   = "${local.name}-migration"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{ name = "migration", image = var.image, essential = true, user = "10001:10001", command = ["python", "-m", "planner.deployment.migrate"],
    environment = concat([for e in local.environment : e if e.name != "PLANNER_DATABASE_USERNAME"], [{ name = "PLANNER_DATABASE_USERNAME", value = "planner_admin" }]),
  secrets = [{ name = "PLANNER_DATABASE_PASSWORD", valueFrom = "${aws_db_instance.app.master_user_secret[0].secret_arn}:password::" }, { name = "PLANNER_APPLICATION_PASSWORD", valueFrom = "${aws_secretsmanager_secret.application.arn}:password::" }], logConfiguration = local.logging }])

}

resource "aws_budgets_budget" "monthly" {

  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {

    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {

    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }


}

resource "aws_cloudwatch_metric_alarm" "api_unhealthy" {

  alarm_name          = "${local.name}-unhealthy-api"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { LoadBalancer = aws_lb.app.arn_suffix, TargetGroup = aws_lb_target_group.api.arn_suffix }
  alarm_actions       = [aws_sns_topic.operations.arn]

}


resource "aws_sns_topic" "operations" {
  name              = "${local.name}-operations"
  kms_master_key_id = "alias/aws/sns"
}
resource "aws_sns_topic_subscription" "operations" {
  topic_arn = aws_sns_topic.operations.arn
  protocol  = "email"
  endpoint  = var.budget_email
}
resource "aws_cloudwatch_metric_alarm" "queue" {
  alarm_name          = "${local.name}-old-pending"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "planner.queue.oldest_age"
  namespace           = "AdaptivePlanner"
  period              = 60
  statistic           = "Maximum"
  threshold           = 30
  treat_missing_data  = "notBreaching"
  dimensions          = { "service.name" = "planner-api" }
  alarm_actions       = [aws_sns_topic.operations.arn]
}
resource "aws_cloudwatch_metric_alarm" "database" {
  alarm_name          = "${local.name}-database-unavailable"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "planner.db.reachable"
  namespace           = "AdaptivePlanner"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  dimensions          = { "service.name" = "planner-api" }
  alarm_actions       = [aws_sns_topic.operations.arn]
}
resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.name}-operations"
  dashboard_body = jsonencode({ widgets = [
    for index, item in [
      ["Queue age", "planner.queue.oldest_age"],
      ["Database reachability", "planner.db.reachable"],
      ["Expired leases", "planner.jobs.expired_leases"],
      ["Calendar lag", "planner.calendar.lag"],
      ["Calendar conflicts", "planner.calendar.conflicts"],
      ["Model spend micro USD", "planner.model.spend_microusd"]
    ] : { type = "metric", x = (index % 2) * 12, y = floor(index / 2) * 6, width = 12, height = 6, properties = { title = item[0], region = var.region, metrics = [["AdaptivePlanner", item[1], "service.name", "planner-api"]], period = 60, stat = "Maximum" } }
  ] })
}
