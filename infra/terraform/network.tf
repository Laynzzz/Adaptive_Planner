data "aws_availability_zones" "available" {

  state = "available"
}

data "aws_caller_identity" "current" {

}

resource "aws_vpc" "app" {

  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = local.name }

}

resource "aws_internet_gateway" "app" {

  vpc_id = aws_vpc.app.id
}

resource "aws_subnet" "public" {

  count                   = 2
  vpc_id                  = aws_vpc.app.id
  cidr_block              = cidrsubnet(aws_vpc.app.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

}

resource "aws_subnet" "database" {

  count                   = 2
  vpc_id                  = aws_vpc.app.id
  cidr_block              = cidrsubnet(aws_vpc.app.cidr_block, 8, count.index + 10)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

}

resource "aws_route_table" "public" {

  vpc_id = aws_vpc.app.id
  route {

    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.app.id
  }


}

resource "aws_route_table_association" "public" {

  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {

  name_prefix = "${local.name}-alb-"
  vpc_id      = aws_vpc.app.id
  ingress {

    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {

    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.app.cidr_block]
  }


}

resource "aws_security_group" "task" {

  name_prefix = "${local.name}-task-"
  vpc_id      = aws_vpc.app.id
  ingress {

    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {

    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }


}

resource "aws_security_group" "database" {

  name_prefix = "${local.name}-db-"
  vpc_id      = aws_vpc.app.id
  ingress {

    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.task.id]
  }


}

resource "aws_lb" "app" {

  name                       = local.name
  load_balancer_type         = "application"
  subnets                    = aws_subnet.public[*].id
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection

}

resource "aws_lb_target_group" "api" {

  name                 = local.name
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = aws_vpc.app.id
  deregistration_delay = 15
  health_check {

    path                = "/health/ready"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 15
    timeout             = 5
  }


}

resource "aws_lb_listener" "https" {

  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {

    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }


}

