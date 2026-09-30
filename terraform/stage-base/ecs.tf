resource "aws_ecs_cluster" "this" {
  name = "wfm-stage"

  # Metricile detaliate costa; log-urile merg oricum in CloudWatch
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

# FARGATE_SPOT ramane disponibil in cluster, dar serviciile folosesc FARGATE:
# imaginile sunt ARM64 (Graviton), iar Fargate Spot nu suporta ARM64
resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}
