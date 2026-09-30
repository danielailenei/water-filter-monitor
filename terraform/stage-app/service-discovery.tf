# Namespace DNS privat: Cloud Map creeaza in spate o zona Route 53 privata in VPC-ul stage
resource "aws_service_discovery_private_dns_namespace" "this" {
  name        = "wfm.local"
  description = "DNS intern pentru serviciile ECS din stage"
  vpc         = local.base.vpc_id
}

locals {
  # Doar serviciile apelate de alte containere; backend si grafana se acceseaza prin ALB
  discoverable_services = ["mosquitto", "influxdb"]
}

# <serviciu>.wfm.local -> IP-urile taskurilor care ruleaza (ECS le inregistreaza automat)
resource "aws_service_discovery_service" "app" {
  for_each = toset(local.discoverable_services)

  name = each.key

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.this.id
    routing_policy = "MULTIVALUE"

    dns_records {
      type = "A"
      ttl  = 10
    }
  }

  # ECS raporteaza sanatatea taskurilor; un task nesanatos iese din DNS
  health_check_custom_config {}
}
