# Autoscaling doar pentru backend: e stateless, iar ALB-ul imparte singur traficul.
# (mosquitto/influxdb au stare, sensor ar dubla datele)

# Ce scalam si intre ce limite
resource "aws_appautoscaling_target" "backend" {
  service_namespace  = "ecs"
  resource_id        = "service/${local.base.ecs_cluster_name}/${aws_ecs_service.app["backend"].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3 # plafon de cost
}

# "Termostat": tine CPU-ul mediu al serviciului la ~50%.
# AWS creeaza singur alarmele CloudWatch (AlarmHigh ~3 min, AlarmLow ~15 min).
resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "wfm-stage-backend-cpu50"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.backend.service_namespace
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = 50
    scale_out_cooldown = 60  # dupa un scale out, asteapta 1 min sa vada efectul
    scale_in_cooldown  = 120 # micsorare prudenta, fara oscilatii

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
