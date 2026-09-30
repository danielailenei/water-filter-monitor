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

  # Fara health_check_custom_config: blocul gol nu ajunge in AWS si provider-ul 6
  # ar cere inlocuirea serviciului la fiecare plan. ECS tot inregistreaza IP-ul
  # la pornirea taskului si il scoate la oprire.
}
