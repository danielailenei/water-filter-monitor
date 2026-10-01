locals {
  # Servicii cu o singura instanta, oprita inainte de pornirea celei noi (vezi mai jos)
  singletons = ["influxdb", "sensor", "worker"]
}

resource "aws_ecs_service" "app" {
  for_each = local.services

  name            = each.key
  cluster         = local.base.ecs_cluster_name
  task_definition = aws_ecs_task_definition.app[each.key].arn
  desired_count   = 1

  # Taskurile Fargate (unde e costul) primesc tag-urile serviciului (Project/Layer)
  # -> costul ECS apare pe tag-uri in Cost Explorer; plus tag-uri aws:ecs:* de la ECS
  propagate_tags          = "SERVICE"
  enable_ecs_managed_tags = true

  capacity_provider_strategy {
    capacity_provider = "FARGATE" # nu FARGATE_SPOT: Spot nu suporta ARM64
    weight            = 1
  }

  network_configuration {
    subnets          = local.base.private_subnet_ids
    security_groups  = [local.base.app_security_group_ids[each.key]]
    assign_public_ip = false # iesire doar prin NAT
  }

  # Servicii care trebuie sa ruleze EXACT o instanta -> la deploy opreste vechiul, apoi porneste noul:
  #  - influxdb: doua taskuri pe acelasi EFS ar corupe baza de date
  #  - sensor: doi senzori (filtru vechi infundat + filtru nou) publica alternativ
  #    presiuni mari/mici -> alertele se reseteaza si se retrimit la fiecare citire
  #  - worker: doi workeri ar scrie de doua ori fiecare citire si ar trimite alertele dublu
  deployment_minimum_healthy_percent = contains(local.singletons, each.key) ? 0 : 100
  deployment_maximum_percent         = contains(local.singletons, each.key) ? 100 : 200
  # Redistribuirea taskurilor intre AZ-uri cere maximum > 100%; la un singur task n-are ce muta
  availability_zone_rebalancing = contains(local.singletons, each.key) ? "DISABLED" : "ENABLED"

  # Deploy esuat -> revine automat la revizia anterioara
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  enable_execute_command = true # shell in container (task role din 6.2)

  # Doar mosquitto si influxdb apar in DNS (6.3)
  dynamic "service_registries" {
    for_each = contains(keys(aws_service_discovery_service.app), each.key) ? [1] : []

    content {
      registry_arn = aws_service_discovery_service.app[each.key].arn
    }
  }

  # Doar backend si grafana primesc trafic de la ALB; ECS le inregistreaza singur IP-urile
  dynamic "load_balancer" {
    for_each = contains(keys(local.alb_targets), each.key) ? [1] : []

    content {
      target_group_arn = aws_lb_target_group.app[each.key].arn
      container_name   = each.key
      container_port   = local.alb_targets[each.key].port
    }
  }

  # Timp de gratie la pornire: health check-urile ALB nu omoara taskul cat inca porneste
  # (valid doar pentru servicii cu load balancer)
  health_check_grace_period_seconds = contains(keys(local.alb_targets), each.key) ? 60 : null

  # desired_count e doar valoarea initiala; apoi il gestioneaza autoscaling-ul (autoscaling.tf).
  # Fara asta, orice apply ar readuce fortat backend-ul la 1 task.
  lifecycle {
    ignore_changes = [desired_count]
  }

  # Internet (ECR, SSM, loguri) inainte de pornire; target group-urile legate de ALB
  depends_on = [
    aws_route.private_to_internet,
    aws_lb_listener.http,
    aws_lb_listener_rule.grafana,
    aws_lb_listener_rule.backend,
  ]
}
