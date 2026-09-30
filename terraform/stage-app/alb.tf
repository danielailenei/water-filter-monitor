locals {
  # Serviciile expuse prin ALB: portul containerului + calea de health check
  alb_targets = {
    backend = { port = 8000, health_path = "/health" }
    grafana = { port = 3000, health_path = "/grafana/api/health" }
  }
}

# ---------- ALB public, in subretelele publice (2 AZ) ----------
resource "aws_lb" "this" {
  name               = "wfm-stage-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = local.base.public_subnet_ids
  security_groups    = [local.base.alb_security_group_id] # intrare doar de la CloudFront

  # Respinge cererile cu header-e HTTP invalide (protectie la request smuggling)
  drop_invalid_header_fields = true

  tags = {
    Name = "wfm-stage-alb"
  }
}

# ---------- Target groups: unde trimite ALB-ul traficul ----------
resource "aws_lb_target_group" "app" {
  for_each = local.alb_targets

  name        = "wfm-stage-${each.key}"
  port        = each.value.port
  protocol    = "HTTP"
  target_type = "ip" # taskurile Fargate (awsvpc) se inregistreaza dupa IP
  vpc_id      = local.base.vpc_id

  # Implicit 300 s: la deploy/destroy ALB-ul ar astepta 5 minute dupa fiecare task
  deregistration_delay = 30

  health_check {
    path                = each.value.health_path
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2 # 2 raspunsuri bune -> Healthy (~30 s)
    unhealthy_threshold = 3 # 3 esecuri -> Unhealthy, fara trafic
  }
}

# ---------- Listener HTTP:80 - implicit spre backend (dashboard + API) ----------
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app["backend"].arn
  }
}

# /grafana si /grafana/* -> Grafana (serveste de pe sub-cale, vezi task definition)
resource "aws_lb_listener_rule" "grafana" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app["grafana"].arn
  }

  condition {
    path_pattern {
      values = ["/grafana", "/grafana/*"]
    }
  }
}
