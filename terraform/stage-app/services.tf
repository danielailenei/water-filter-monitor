resource "aws_ecs_service" "app" {
  for_each = local.services

  name            = each.key
  cluster         = local.base.ecs_cluster_name
  task_definition = aws_ecs_task_definition.app[each.key].arn
  desired_count   = 1

  capacity_provider_strategy {
    capacity_provider = "FARGATE" # nu FARGATE_SPOT: Spot nu suporta ARM64
    weight            = 1
  }

  network_configuration {
    subnets          = local.base.private_subnet_ids
    security_groups  = [local.base.app_security_group_ids[each.key]]
    assign_public_ip = false # iesire doar prin NAT
  }

  # InfluxDB: niciodata doua taskuri pe acelasi EFS -> opreste vechiul, apoi porneste noul
  deployment_minimum_healthy_percent = each.key == "influxdb" ? 0 : 100
  deployment_maximum_percent         = each.key == "influxdb" ? 100 : 200

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

  # Taskurile au nevoie de internet (ECR, SSM, loguri) inainte sa porneasca
  depends_on = [aws_route.private_to_internet]
}
